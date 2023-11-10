"use strict";

// Import globals setup
window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.avatars = {};


/**
 * Global and Project Avatars page
 */
App.pages.avatars.init = function(upload_url, page_options) {
    // Initialize page defaults
    this.upload_url = upload_url;
    page_options = page_options || {};
    this.project_id = page_options.project_id || null;
    this.can_user_edit = !!page_options.can_user_edit;

    $('#new_avatar_upload button[type="submit"]').on('click', function(e) {
        e.preventDefault();
        let $form = $('#new_avatar_upload');
        $form.find('.is-invalid').removeClass('is-invalid');    // Clear errors

        // Load values for name/image
        let name = $form.find('input[name="name"]').val();
        let image = $form.find('input[name="image"]')[0].files[0];
        if (!name) {
            $form.find('input[name="name"]').addClass('is-invalid');
            return false;
        }
        if (!image) {
            $form.find('input[name="image"]').addClass('is-invalid');
            return false;
        }

        let form_data = new FormData();
        form_data.append('name', name);
        form_data.append('image', image);
        let avatar_url = $form.attr('action');
        $form.find('button[type="submit"]').attr({disabled: true});
        $.ajax({
            url: avatar_url,
            type: 'POST',
            data: form_data,
            processData: false,
            contentType: false,
            beforeSend: function(xhr) {
                // Attach CSRF Token
                xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
            },
            success: function(data, textStatus, xhr) {
                // TODO: show success message
                window.location.reload();
            },
            error: function(xhr, textStatus, err) {
                console.log("ERROR: Avatar upload error: ", err, xhr);
                let responseText = xhr.responseText;
                try {
                    responseText = JSON.parse(responseText);
                    if (responseText.detail) {
                        $.notify(responseText.detail, {autoHide: false, position: 'top center'});
                    }
                } catch (err) {
                    console.log("Error parsing response as JSON: ", err);
                    $.notify("Error occurred while submitting avatar", {autoHide: false, position: 'top center'});
                }
                $form.find('button[type="submit"]').attr({disabled: false});
            }
        });
    });
    // Click contributor name to quick-add avatar for their name
    $('body').on('click', '.contributor-no-avatar', function(e) {
        // [OLD] Prepopulate form at top
        //$('#avatar_name').val(
        //    $(e.currentTarget).text()
        //).focus();

        // Check if current target popover is already open (and toggle closed)
        if ($(e.currentTarget).data('bs.popover')) {
            $(e.currentTarget).popover('dispose');
            return; // Don't re-open
        } else {
            // Find any other open popovers and destroy them
            $('.popover.avatar-popover').popover('dispose');
        }

        let contributor_name = $(e.currentTarget).text();
        let upload_url = App.pages.avatars.upload_url;
        let popover_html = ''
            + '<div class="dropzone avatar-upload-dropzone"></div>'
            + '<div class="text-center" style="margin-top:2px">'
            +   '<button type="submit" class="btn btn-primary btn-sm submit-dropzone-upload" disabled>Submit</button>'
            +   '<button type="button" class="btn btn-default btn-sm cancel-dropzone-upload" style="position:absolute;bottom:8px"><i class="fa fa-times"></i></button>'
            + '</div>';
        // Open popover with file select form
        let _popover = $(e.currentTarget).popover({
            container: 'body',
            content: popover_html,
            placement: 'top',
            template: '<div class="popover avatar-popover" role="tooltip"><div class="arrow"></div><div class="popover-body"></div></div>',
            html: true,
            sanitize: false,
        });
        _popover.on('shown.bs.popover', function() {
            let $popover = $($(this).data('bs.popover').tip);
            let _dropzone = new window.Dropzone(
                $popover.find('div.avatar-upload-dropzone')[0],
                {
                    url: upload_url,
                    paramName: "image",
                    maxFiles: 1,
                    maxFilesize: 2, // MB
                    acceptedFiles: 'image/*',
                    thumbnailHeight: 70,
                    thumbnailWidth: 70,
                    thumbnailMethod: 'contain',
                    dictDefaultMessage: 'Select Image',
                    autoProcessQueue: false,
                    headers: {
                        "X-CSRFToken": App.utils.getCookie("csrftoken"),
                    },
                    init: function() {
                        this.on("addedfile", function(file) {
                            // NOTE: this will still be called if invalid/too large file selected
                            $popover.find('.submit-dropzone-upload').attr({disabled: false});
                        });
                        this.on("removedfile", function(file) {
                            $popover.find('.submit-dropzone-upload').attr({disabled: true});
                        });
                        this.on("sending", function(file, xhr, formData) {
                            // Append 'name' field to request
                            formData.append('name', contributor_name);
                        });
                        this.on("success", function(file, responseText, e) {
                            // Success (reload the page after animation ends)
                            setTimeout(function() { window.location.reload(); }, 1000);
                        });
                        this.on("error", function(file, message, xhr) {
                            console.log("ERROR: Avatar upload error: ", message, xhr);
                            let responseText = xhr.responseText;
                            try {
                                responseText = JSON.parse(responseText);
                                if (responseText.detail) {
                                    $.notify(responseText.detail, {autoHide: false, position: 'top center'});
                                }
                            } catch (err) {
                                console.log("Error parsing response as JSON: ", err);
                                $.notify("Error occurred while submitting avatar", {autoHide: false, position: 'top center'});
                            }
                        });
                    }
                }
            );

            $popover.find('button.submit-dropzone-upload').on('click', function(e) {
                e.preventDefault();
                _dropzone.processQueue();
            });
            $popover.find('button.cancel-dropzone-upload').on('click', function(e) {
                e.preventDefault();
                // If no file set, close popover
                if (_dropzone.getQueuedFiles().length === 0) {
                    $popover.popover('dispose');
                    return;
                }
                _dropzone.removeAllFiles();
            });
        });
        _popover.popover('show');

    });
    $('body').on('click', '.delete-avatar-btn', function(e) {
        let self = this;

        let avatar_id = $(e.currentTarget).attr('data-avatar-id');
        let avatar_name = $(e.currentTarget).attr('data-avatar-name');
        let project_id = $(e.currentTarget).attr('data-project-id');

        // Determine if this is global/project avatar
        let avatar_url = '/api/v1/avatars/'+avatar_id+'/';
        if (project_id) {
            avatar_url = '/api/v1/projects/'+project_id+'/avatars/'+avatar_id+'/';
        }
        // Set name
        $('#confirm-delete-avatar-modal #confirm-delete-avatar-name').text(avatar_name);
        // Set image preview
        $('#confirm-delete-avatar-modal #confirm-delete-avatar-image').append(
            $(e.currentTarget).parents('.card').find('img')[0].outerHTML
        );
        let $modal = $('#confirm-delete-avatar-modal').modal();
        $modal.on('click', '.confirm-delete', function() {
            // Delete entry
            $.ajax({
                url: avatar_url,
                method: 'DELETE',
                beforeSend: function(xhr) {
                    // Attach CSRF Token
                    xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                },
                success: function(data, textStatus, xhr) {
                    // Remove card from DOM
                    $(e.currentTarget).parents('.card-container').remove();
                    // Dismiss modal
                    $modal.modal('hide');
                    // TODO: show success message
                    window.location.reload();
                },
                error: function(xhr, textStatus, err) {
                    console.log("ERROR: ",err);
                },
            });
        });
        $modal.on('hidden.bs.modal', function() {
            $('#confirm-delete-avatar-modal #confirm-delete-avatar-name').text('');
            $('#confirm-delete-avatar-modal #confirm-delete-avatar-image').text('');
        });
    });
};
