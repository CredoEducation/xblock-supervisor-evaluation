function SupervisorEvaluationEditBlock(runtime, element, params) {
    var gettext = null;
    if ('gettext' in window) {
        gettext = window.gettext;
    }
    if (typeof gettext == "undefined") {
        // No translations -- used by test environment
        gettext = function(string) { return string; };
    }

    var $element = $(element);
    var saveBtn = $element.find('.save-button');
    var errMsgBlock = $element.find('.err-msg');

    if (!saveBtn.hasClass('disabled')) {
        saveBtn.on('click', function() {
            saveBtn.text(gettext('Please, wait...')).addClass('disabled');
            errMsgBlock.hide();

            var display_name = $element.find('#se_display_name').val();
            var evaluation_hash = $element.find('#evaluation_hash').val();
            var links_expiration_date = $element.find('#links_expiration_date').val();
            var links_expiration_time = $element.find('#links_expiration_time').val();
            var email_text = $element.find("#se_email_text").val();
            var profile_fields = $element.find("#profile_fields").val();

            var handlerUrl = runtime.handlerUrl(element, 'update_editor_context');
            runtime.notify('save', {state: 'start', message: gettext("Saving")});

            $.post(handlerUrl, JSON.stringify({
                'display_name': display_name,
                'evaluation_hash': evaluation_hash,
                'links_expiration_date': links_expiration_date,
                'links_expiration_time': links_expiration_time,
                'email_text': email_text,
                'profile_fields': profile_fields
            }), function(res) {
                saveBtn.text(gettext('Save')).removeClass('disabled');
                if (res.result === 'success') {
                    runtime.notify('save', {state: 'end'});
                } else if (res.result === 'error') {
                    errMsgBlock.show().text(gettext('Error:') + ' ' + res.msg);
                    runtime.notify('error', {
                        'title': gettext("There was an error with your form."),
                        'message': res.msg
                    });
                }
            });
        });
    }

    $element.find('.cancel-button').on('click', function() {
        runtime.notify('cancel', {});
    });

    $element.find('#links_expiration_date').datepicker();
    $element.find('#links_expiration_time').timepicker({timeFormat: 'H:i'});


}
