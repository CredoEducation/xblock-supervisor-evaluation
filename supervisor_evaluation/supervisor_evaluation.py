from __future__ import absolute_import
import datetime
import re
import uuid

from xblock.core import XBlock
from xblock.fields import Boolean, Integer, List, Scope, String, Dict
from xblockutils.settings import XBlockWithSettingsMixin
from web_fragments.fragment import Fragment
from xblockutils.resources import ResourceLoader
from xmodule.modulestore.django import modulestore
from django.conf import settings
from django.core import mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
try:
    from common.djangoapps.credo_modules.models import SupervisorEvaluationInvitation
except ImportError:
    SupervisorEvaluationInvitation = None
try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None

loader = ResourceLoader(__name__)

_ = lambda text: text


class DummyTranslationService(object):
    """
    Dummy drop-in replacement for i18n XBlock service
    """
    gettext = _


@XBlock.wants('settings')
@XBlock.needs('i18n')
@XBlock.needs("user")
@XBlock.needs("user_state")
class SupervisorEvaluationBlock(XBlockWithSettingsMixin, XBlock):
    display_name = String(
        display_name=_("Display Name"),
        help=_("The display name for this component."),
        scope=Scope.settings,
        default=_("Supervisor Evaluation"),
    )

    evaluation_block_unique_id = String(
        display_name=_("Block ID with questions for evaluation"),
        help=_("Block ID with questions for evaluation"),
        scope=Scope.settings,
    )

    links_expiration_date = String(
        display_name=_("Links expiration date"),
        help=_("Links expiration date"),
        scope=Scope.settings,
    )

    email_text = String(
        display_name=_("Email text"),
        help=_("Email text"),
        scope=Scope.settings,
        default=_("Hello!\n\n%student_name% asked you to provide feedback: %link%"),
    )

    url_hash = String(
        default=None,
        scope=Scope.user_state,
        help="URL hash."
    )

    block_settings_key = 'supervisor-evaluation'

    @property
    def course_id(self):
        return self.xmodule_runtime.course_id  # pylint: disable=no-member

    @property
    def i18n_service(self):
        """ Obtains translation service """
        i18n_service = self.runtime.service(self, "i18n")
        if i18n_service:
            return i18n_service
        else:
            return DummyTranslationService()

    @property
    def has_author_view(self):
        return True

    def _create_fragment(self, template, js_url=None, initialize_js_func=None):
        fragment = Fragment()
        fragment.add_content(template)
        if initialize_js_func:
            fragment.initialize_js(initialize_js_func, {})
        if js_url:
            fragment.add_javascript_url(self.runtime.local_resource_url(self, js_url))
        fragment.add_css_url(self.runtime.local_resource_url(self, 'public/css/se_block.css'))
        return fragment

    def get_real_user(self):
        anonymous_user_id = self.xmodule_runtime.anonymous_student_id
        user = self.xmodule_runtime.get_real_user(anonymous_user_id)
        return user

    def get_supervisor_evaluation_url(self, url_hash):
        lms_url = configuration_helpers.get_value('LMS_ROOT_URL', settings.LMS_ROOT_URL)
        link_url = lms_url + reverse('supervisor_evaluation_block', kwargs={
            'hash_id': url_hash
        })
        return link_url

    def student_view(self, context=None):
        if SupervisorEvaluationInvitation is None:
            raise Exception("SupervisorEvaluationInvitation can't be imported")

        is_studio_view = self.xmodule_runtime.get_real_user is None
        invitation = None
        supervisor_evaluation_url = ''

        if not is_studio_view and self.url_hash:
            user = self.get_real_user()
            invitation = SupervisorEvaluationInvitation.objects.filter(
                evaluation_block_id=str(self.location),
                student=user,
                url_hash=self.url_hash
            ).first()
            if invitation:
                supervisor_evaluation_url = self.get_supervisor_evaluation_url(self.url_hash)

        context_dict = {
            'evaluation_block_unique_id': self.evaluation_block_unique_id,
            'is_studio_view': is_studio_view,
            'invitation': invitation,
            'supervisor_evaluation_url': supervisor_evaluation_url
        }
        template = loader.render_django_template("/templates/public.html", context=context_dict,
                                                 i18n_service=self.i18n_service)
        return self._create_fragment(template, js_url='public/js/se_public.js',
                                     initialize_js_func='SupervisorEvaluationDisplayBlock')

    def author_view(self, context=None):
        return self.student_view()

    def studio_view(self, context=None):
        survey_blocks = []
        with modulestore().bulk_operations(self.runtime.course_id):
            sequential_blocks = modulestore().get_items(
                self.runtime.course_id, qualifiers={'category': 'sequential'}
            )
            for seq in sequential_blocks:
                if seq.use_as_survey_for_supervisor and seq.supervisor_evaluation_hash:
                    survey_blocks.append({
                        'title': seq.get_parent().display_name + ' / ' + seq.display_name,
                        'evaluation_hash': str(seq.supervisor_evaluation_hash)
                    })

        links_expiration_date, links_expiration_time = '', ''
        if self.links_expiration_date:
            links_expiration_lst = self.links_expiration_date.split(' ')
            if len(links_expiration_lst) > 1:
                links_expiration_date, links_expiration_time = links_expiration_lst[0], links_expiration_lst[1]
            else:
                links_expiration_date, links_expiration_time = links_expiration_lst[0], ''

        context_dict = {
            'survey_blocks': survey_blocks,
            'evaluation_block_unique_id': self.evaluation_block_unique_id,
            'links_expiration_date': links_expiration_date,
            'links_expiration_time': links_expiration_time,
            'email_text': self.email_text
        }
        template = loader.render_django_template("/templates/staff.html", context=context_dict,
                                                 i18n_service=self.i18n_service)
        return self._create_fragment(template, js_url='public/js/se_staff.js',
                                     initialize_js_func='SupervisorEvaluationEditBlock')

    @XBlock.json_handler
    def update_editor_context(self, data, suffix=''):  # pylint: disable=unused-argument
        evaluation_hash = data.get('evaluation_hash')
        if not evaluation_hash:
            return {
                'result': 'error',
                'msg': self.i18n_service.gettext('Evaluation hash is not set')
            }

        email_text = data.get('email_text')
        if not email_text:
            return {
                'result': 'error',
                'msg': self.i18n_service.gettext('Email Text is not set')
            }
        elif '%link%' not in self.email_text:
            return {
                'result': 'error',
                'msg': self.i18n_service.gettext("Email Text must contains '%links%' word")
            }

        links_expiration_date = data.get('links_expiration_date')
        links_expiration_time = data.get('links_expiration_time')
        if links_expiration_date:
            links_expiration_date_regex = re.compile('[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}')
            match = links_expiration_date_regex.match(str(links_expiration_date))
            if not match:
                return {
                    'result': 'error',
                    'msg': self.i18n_service.gettext('Invalid date format')
                }

            if links_expiration_time:
                links_expiration_time_regex = re.compile('[0-2][0-9]:(0|3)0')
                match = links_expiration_time_regex.match(str(links_expiration_time))
                if not match:
                    return {
                        'result': 'error',
                        'msg': self.i18n_service.gettext('Invalid time format')
                    }
                links_expiration_date = links_expiration_date + ' ' + links_expiration_time

        self.evaluation_block_unique_id = evaluation_hash
        self.email_text = email_text

        if links_expiration_date:
            self.links_expiration_date = links_expiration_date

        return {
            'result': 'success'
        }

    @XBlock.json_handler
    def send_email(self, data, suffix=''):
        if SupervisorEvaluationInvitation is None:
            raise Exception("SupervisorEvaluationInvitation can't be imported")

        email = data.get('email')
        user = self.get_real_user()
        course_id = str(self.xmodule_runtime.course_id)
        evaluation_block_id = str(self.location)

        try:
            validate_email(email)
        except ValidationError:
            return {
                'result': 'error',
                'msg': self.i18n_service.gettext('Please, enter valid email address')
            }

        invitation = SupervisorEvaluationInvitation.objects.filter(
            student=user,
            evaluation_block_id=evaluation_block_id
        ).first()
        if invitation:
            return {
                'result': 'error',
                'msg': self.i18n_service.gettext('You have already sent invitation')
            }

        expiration_date = None

        if self.links_expiration_date:
            links_expiration_lst = self.links_expiration_date.split(' ')
            if len(links_expiration_lst) > 1:
                expiration_date = datetime.datetime.strptime(self.links_expiration_date, '%m/%d/%Y %H:%M')
            else:
                expiration_date = datetime.datetime.strptime(self.links_expiration_date, '%m/%d/%Y')

        url_hash = str(uuid.uuid4())

        student_name = user.first_name + ' ' + user.last_name
        student_name = student_name.strip()
        if not student_name:
            student_name = user.username
        student_name = student_name + ' (' + user.email + ')'

        supervisor_evaluation_url = self.get_supervisor_evaluation_url(url_hash)
        text_email = self.email_text.replace('%student_name%', student_name)\
            .replace('%link%', supervisor_evaluation_url)
        html_email = text_email.replace('\n', '<br>')

        from_address = configuration_helpers.get_value('email_from_address', settings.BULK_EMAIL_DEFAULT_FROM_EMAIL)

        with transaction.atomic():
            email_parts = email.split('@')
            email_part1 = email_parts[0][0] + '*' * (len(email_parts[0]) - 1)
            email_part2 = '.'.join(email_parts[1].split('.')[0:-1])
            email_part2 = '*' * (len(email_part2) - 1) + email_part2[-1]
            email_cut = email_part1 + '@' + email_part2 + '.' + email_parts[1].split('.')[-1]
            se_obj = SupervisorEvaluationInvitation(
                url_hash=url_hash,
                course_id=course_id,
                evaluation_block_id=evaluation_block_id,
                student=user,
                email=email_cut,
                expiration_date=expiration_date
            )
            se_obj.save()
            mail.send_mail('Supervisor Evaluation', text_email, from_address, [email],
                           fail_silently=False, html_message=html_email)
            self.url_hash = url_hash

        return {
            'result': 'success',
            'msg': self.i18n_service.gettext('Invitation was successfully sent')
        }
