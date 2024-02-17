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
    this.page_type = 'global';
    this.project_id = page_options.project_id || null;
    if (this.project_id !== null) {
        this.page_type = 'project';
    }
    this.avatars_list = page_options.avatars_list || [];
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

    // Change avatar image (existing entry)
    $('body').on('click', '.change-avatar-btn', function(e) {
        // Locate parent `.card` and ensure dropzone not rendered
        let $card = $(e.currentTarget).parents('.card');
        if ($card.length === 0 ) { return; }
        if ($card.find('.avatar-change-image-overlay').length > 0) {
            return;     // Already open
        }

        let contributor_name = $(e.currentTarget).text();
        let avatar_id = $(e.currentTarget).attr('data-avatar-id');
        // Optional
        let project_id = $(e.currentTarget).attr('data-project-id');
        if (!avatar_id) {
            return;
        }

        let upload_url;
        if (project_id) {
            upload_url = "/api/v1/projects/"+project_id+"/avatars/"+avatar_id+"/";
        } else {
            upload_url = "/api/v1/avatars/"+avatar_id+"/";
        }
        let dropzone_html = ''
            +'<div class="avatar-change-image-overlay">'
            + '<div class="text-center" style="margin-top:2px">'
            +   '<button type="submit" class="btn btn-primary btn-sm submit-dropzone-upload" disabled>Submit</button>'
            +   '<button type="button" class="btn btn-default btn-sm cancel-dropzone-upload" style="margin-right:-18px;"><i class="fa fa-times"></i></button>'
            + '</div>'

            + '<div class="dropzone avatar-upload-dropzone"></div>'
            +'</div>';
        $card.prepend(dropzone_html);
        let _dropzone = new window.Dropzone(
            $card.find('div.avatar-upload-dropzone')[0],
            {
                url: upload_url,
                method: "put",
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
                        $card.find('.submit-dropzone-upload').attr({disabled: false});
                    });
                    this.on("removedfile", function(file) {
                        $card.find('.submit-dropzone-upload').attr({disabled: true});
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

        $card.find('button.submit-dropzone-upload').on('click', function(e) {
            e.preventDefault();
            _dropzone.processQueue();
        });
        $card.find('button.cancel-dropzone-upload').on('click', function(e) {
            e.preventDefault();
            $card.find('.avatar-change-image-overlay').remove();
            _dropzone.removeAllFiles();
            _dropzone.destroy();
        });
    });

    // Alias popover
    $('body').on('click', '.avatar-alias-button a', function(e) {
        // Check if current target popover is already open (and toggle closed)
        if ($(e.currentTarget).data('bs.popover')) {
            $(e.currentTarget).popover('dispose');
            return; // Don't re-open
        } else {
            // Find any other open popovers and destroy them
            $('.popover.avatar-alias-popover').popover('dispose');
        }

        let avatar_id = $(e.currentTarget).attr('data-avatar-id');
        let avatar_type = $(e.currentTarget).attr('data-avatar-type');
        let avatar_obj = App.pages.avatars.get_avatar_by_id(avatar_type, avatar_id);
        if (!avatar_obj) {
            console.log('[ERROR] No avatar found matching type="'+avatar_type+'", ID='+avatar_id);
            return false;
        }

        const _get_popover_html = function() {
            let popover_html = '';
            if (App.pages.avatars.can_user_edit) {
                if (avatar_obj.type == App.pages.avatars.page_type) {
                    popover_html += '<div class="add-avatar-alias-container">'
                                  +   '<div class="input-group input-group-sm">'
                                  +     '<input type="text" class="form-control add-avatar-alias-name" placeholder="New Alias" />'
                                  +     '<div class="input-group-append">'
                                  +       '<button class="btn btn-primary add-avatar-alias-name-btn" role="button">Add</button>'
                                  +     '</div>'
                                  +   '</div>'
                                  + '</div>';
                } else {
                    popover_html += '<div>This is a <a href="/avatars/">global avatar</a>.</div>';
                }
                popover_html += '<hr />';
            }
            if (avatar_obj['aliases'].length === 0) {
                popover_html += '<i class="text-muted">No aliases yet.</i>';
            } else {
                popover_html += '<ul>';
                _.each(avatar_obj['aliases'], function(item) {
                    let action_html = '';
                    if (App.pages.avatars.can_user_edit
                            && avatar_obj.type == App.pages.avatars.page_type) {
                        action_html += '<a class="text-danger btn btn-sm btn-link delete-avatar-alias-btn" title="Delete this alias"><i class="fa fa-times"></i></a>';
                    }
                    popover_html += '<li data-alias-id="'+item.id+'">'
                                  +   _.escape(item.name)
                                  +   action_html
                                  + '</li>';
                });
                popover_html += '</ul>';
            }
            return popover_html;
        };
        // Open popover with list of aliases
        let _popover = $(e.currentTarget).popover({
            container: 'body',
            content: _get_popover_html(),
            placement: 'right',
            template: '<div class="popover avatar-alias-popover" role="tooltip"><div class="arrow"></div><div class="popover-body"></div></div>',
            html: true,
            sanitize: false,
        });
        _popover.on('shown.bs.popover', function() {
            let $popover = $($(this).data('bs.popover').tip);
            $popover.on('click', '.delete-avatar-alias-btn', function(e) {
                let alias_id = $(e.currentTarget).parent().attr('data-alias-id');
                if (!alias_id) {
                    return false;
                }

                // Send to server
                alias_id = parseInt(alias_id);
                let alias_url;
                if (avatar_obj.type == 'project') {
                    alias_url = '/api/v1/projects/'+avatar_obj.project_id+'/avatars/'+avatar_obj.id+'/aliases/'+alias_id+'/';
                } else {
                    alias_url = '/api/v1/avatars/'+avatar_obj.id+'/aliases/'+alias_id+'/';
                }

                $.ajax({
                    url: alias_url,
                    method: 'DELETE',
                    contentType: 'application/json',
                    beforeSend: function(xhr) {
                        // Attach CSRF Token
                        xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                    },
                    success: function(data, textStatus, xhr) {
                        $.notify("Alias removed successfully.", {className: "success", position: "top right"});
                        // Remove from aliases list
                        let alias_model = _.findWhere(avatar_obj.aliases, {id: alias_id});
                        if (alias_model) {
                            avatar_obj.aliases.splice(_.indexOf(avatar_obj.aliases, alias_model), 1);
                        }
                        // Re-render popover contents
                        $popover.find('.popover-body').html(
                            _get_popover_html()
                        );
                        // Update count on popover panel
                        if (avatar_obj.aliases.length === 0) {
                            _popover.parent().addClass('show-hover');
                            _popover.html('<i class="fa fa-plus"></i>');
                        } else {
                            _popover.parent().removeClass('show-hover');
                            _popover.text('(+'+avatar_obj.aliases.length+')');
                        }
                    },
                    error: function(xhr, textStatus, err) {
                        console.log('[ERROR] Failed to remove '+avatar_obj.type+' alias for ID='+avatar_obj.id, err, xhr);
                        let error_message = err;
                        try {
                            if (xhr.responseJSON && xhr.responseJSON.detail) {
                                error_message = xhr.responseJSON.detail;
                            }
                        } catch (e) {}
                        $.notify("Error removing alias: "+error_message, {className: "error", position: "top right"});
                    },
                });

            });
            const _submit_alias = function() {
                $popover.find('.is-invalid').removeClass('is-invalid');    // Clear errors
                let name = $popover.find('.add-avatar-alias-name').val().trim();
                if (!name) {
                    $popover.find('.add-avatar-alias-name').addClass('is-invalid');
                    return;
                }

                // Send to server
                let aliases_url;
                if (avatar_obj.type == 'project') {
                    aliases_url = '/api/v1/projects/'+avatar_obj.project_id+'/avatars/'+avatar_obj.id+'/aliases/';
                } else {
                    aliases_url = '/api/v1/avatars/'+avatar_obj.id+'/aliases/';
                }
                let data = {name: name};
                $popover.find('.add-avatar-alias-name-btn').attr({disabled: true});

                $.ajax({
                    url: aliases_url,
                    method: 'POST',
                    data: JSON.stringify(data),
                    contentType: 'application/json',
                    beforeSend: function(xhr) {
                        // Attach CSRF Token
                        xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                    },
                    success: function(data, textStatus, xhr) {
                        $.notify("Alias added successfully.", {className: "success", position: "top right"});
                        // Add to avatar aliases list
                        avatar_obj.aliases.push(data);
                        // Re-render popover contents
                        $popover.find('.popover-body').html(
                            _get_popover_html()
                        );
                        // Update count on popover panel
                        _popover.parent().removeClass('show-hover');
                        _popover.text('(+'+avatar_obj.aliases.length+')');
                    },
                    error: function(xhr, textStatus, err) {
                        console.log('[ERROR] Failed to save new '+avatar_obj.type+' alias for ID='+avatar_obj.id, err, xhr);
                        let error_message = err;
                        try {
                            if (xhr.responseJSON && xhr.responseJSON.detail) {
                                error_message = xhr.responseJSON.detail;
                            }
                        } catch (e) {}
                        $.notify("Error adding alias: "+error_message, {className: "error", position: "top right"});
                    },
                    complete: function() {
                        $popover.find('.add-avatar-alias-name-btn').attr({disabled: false});
                    },
                });
            };
            // Bind click/keyup events for submitting alias
            $popover.on('click', '.add-avatar-alias-name-btn', function(e) {
                _submit_alias();
            });
            $popover.on('keyup', 'input.add-avatar-alias-name', function(e) {
                if (e.key === 'Enter' || e.keyCode === 13) {
                    _submit_alias();
                }
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
App.pages.avatars.get_avatar_by_id = function(avatar_type, avatar_id) {
    let model;
    for (let i = 0; i < App.pages.avatars.avatars_list.length; i++) {
        model = App.pages.avatars.avatars_list[i];
        if (model.type == avatar_type && model.id == avatar_id) {
            return model;
        }
    }
    return null;
}
App.pages.avatars.get_global_avatar_by_id = function(avatar_id) {
    return App.pages.avatars.get_avatar_by_id("global", avatar_id);
};
App.pages.avatars.get_project_avatar_by_id = function(avatar_id) {
    return App.pages.avatars.get_avatar_by_id("project", avatar_id);
};
