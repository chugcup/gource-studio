"use strict";

// Import globals setup
window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.project_builds = {};


/**
 * Project Builds page
 */
App.pages.project_builds.init = function(project_id, page_options) {
    // Initialize page defaults
    this.project_id = project_id;
    page_options = page_options || {};
    this.can_user_edit = !!page_options.can_user_edit;

    // Queue build handler
    const queue_project_build = this.queue_project_build = function(options) {
        options = options || {};
        $('body #queue-project-build-modal .error-message').text('');
        return $.ajax({
            url: "/api/v1/projects/{{project.id}}/builds/new/",
            method: 'POST',
            data: JSON.stringify(options),
            contentType: 'application/json',
            beforeSend: function(xhr) {
                // Attach CSRF Token
                xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
            },
            success: function(data, textStatus, xhr) {
                console.log("SUCCESS: ", data);
                // Redirect/reload
                window.location = '/projects/{{project.id}}/builds/';
            },
            error: function(xhr, textStatus, err) {
                // Error
                console.log("Queue error: "+err, xhr);
                if (xhr.responseJSON) {
                    for (let key in xhr.responseJSON) {
                        $('body #queue-project-build-modal .error-message').text(xhr.responseJSON[key]);
                    }
                } else {
                    $('body #queue-project-build-modal .error-message').text(err);
                }
            }
        });
    };
    $('body').on('click', '.queue-project-build-btn', function(e) {
        $('#queue-project-build-modal').modal();
    });
    $('body #queue-project-build-modal').on('click', '.btn-primary', function() {
        let options = {};
        if ($('#queue_project_build_refetch_log').is(':checked')) {
            options.refetch_log = true;
        }
        let $ajax = queue_project_build(options);
    });

    // Delete build handler
    $('body').on('click', '.delete-build-btn', function(e) {
        let project_id = $(e.currentTarget).data('project-id');
        let build_id = $(e.currentTarget).data('build-id');
        if (!project_id || !build_id) {
            return false;
        }
        let confirm_delete = confirm("Delete this build?");
        if (confirm_delete) {
            App.debug && console.log("Deleting build...");
            $.ajax({
                url: "/api/v1/projects/"+project_id+"/builds/"+build_id+"/",
                method: 'DELETE',
                beforeSend: function(xhr) {
                    // Attach CSRF Token
                    xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                },
                success: function(data, textStatus, xhr) {
                    // Redirect/reload
                    window.location.reload();
                },
                error: function(xhr, textStatus, err) {
                    // Error
                    console.log("Delete error: "+err, xhr);
                }
            });
        }
    });
    // Cancel/Abort (running) build handler
    const set_build_status = this.set_build_status = function(project_id, build_id, status) {
        console.log("Setting build to '"+status+"'...");
        $.ajax({
            url: "/api/v1/projects/"+project_id+"/builds/"+build_id+"/",
            method: 'PATCH',
            data: JSON.stringify({
                status: status,
            }),
            contentType: "application/json",
            dataType: "json",
            beforeSend: function(xhr) {
                // Attach CSRF Token
                xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
            },
            success: function(data, textStatus, xhr) {
                // Redirect/reload
                window.location.reload();
            },
            error: function(xhr, textStatus, err) {
                // Error
                console.log(status+" error: "+err, xhr);
            }
        });
    };
    $('body').on('click', '.cancel-build-btn', function(e) {
        let project_id = $(e.currentTarget).data('project-id');
        let build_id = $(e.currentTarget).data('build-id');
        if (!project_id || !build_id) {
            return false;
        }
        let confirm_cancel = confirm("Cancel this build?");
        if (confirm_cancel) {
            set_build_status(project_id, build_id, "canceled");
        }
    });
    $('body').on('click', '.abort-build-btn', function(e) {
        let project_id = $(e.currentTarget).data('project-id');
        let build_id = $(e.currentTarget).data('build-id');
        if (!project_id || !build_id) {
            return false;
        }
        let confirm_abort = confirm("Abort this build?");
        if (confirm_abort) {
            set_build_status(project_id, build_id, "aborted");
        }
    });
};
