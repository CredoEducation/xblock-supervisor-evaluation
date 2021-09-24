function SupervisorEvaluationDisplayBlock(runtime, element, params) {
    var gettext = null;
    if ('gettext' in window) {
        gettext = window.gettext;
    }
    if (typeof gettext == "undefined") {
        // No translations -- used by test environment
        gettext = function(string) { return string; };
    }

    var $element = $(element);
    var mainBlock = $element.find('.se_send_email_block');
    var errBlock = $element.find('.se_error_msg');
    var sendEmailInput = $element.find('.se_send_email_input');
    var sendEmailBtn = $element.find('.se_send_email_btn');
    var initUrl = runtime.handlerUrl(element, 'xblock_init');

    $.post(initUrl, JSON.stringify({}), function (res) {
        $element.find('.invitation_loading').hide();
        if (res.result) {
            $element.find('.invitation_sent').show().html(
                '<div class="se_invitation_sent">' + gettext('You have already sent invitation to this email: ') + res.invitation.email  + '</div>\n' +
                '<div class="se_invitation_link">' + gettext('You may provide the link to your mentor manually: ') + '<a href="' + res.link + '" target="_blank">' + res.link + '</a></div>'
            );
        } else {
            $element.find('.invitation_email_block').show();
            sendEmailBtn.on('click', function() {
                var handlerUrl = runtime.handlerUrl(element, 'send_email');
                errBlock.hide();

                $.post(handlerUrl, JSON.stringify({
                    email: sendEmailInput.val()
                }), function (res) {
                    sendEmailBtn.text(gettext('Send')).removeClass('disabled');
                    if (res.result === 'success') {
                        mainBlock.html('<span style="color: green;">' + res.msg + '</span>');
                    } else if (res.result === 'error') {
                        errBlock.show().text(gettext('Error:') + ' ' + res.msg);
                    }
                });
            });
        }
    });
}
