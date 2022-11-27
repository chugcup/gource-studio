"use strict";

// Import globals setup
window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.build_queue = {};


/**
 * Global Build Queue page
 */
App.pages.build_queue.init = function(page_options) {
    // Initialize page defaults
    page_options = page_options || {};

    // Delete build handler
    $('body').on('click', '.delete-build-btn', function(e) {
        let project_id = $(e.currentTarget).data('project-id');
        let build_id = $(e.currentTarget).data('build-id');
        if (!project_id || !build_id) {
            return false;
        }
        let confirm_delete = confirm("Delete this build?");
        if (confirm_delete) {
            console.log("Deleting build...");
            $.ajax({
                url: "/api/v1//projects/"+project_id+"/builds/"+build_id+"/",
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
    let set_build_status = function(project_id, build_id, status) {
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
