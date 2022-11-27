"use strict";

// Import globals setup
window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.new_project = {};


/**
 * New Project page
 */
App.pages.new_project.init = function(page_options) {
    // Initialize page defaults
    page_options = page_options || {};

    // Listen for VCS option changes
    $('body').on('change', '#project-vcs-select', function(e) {
        // Change 'branch' default input if VCS is changed
        if ($(e.currentTarget).val() == 'hg') {
            // Mercurial
            $('#project-branch-input').val('default');
        } else {
            // Git
            $('#project-branch-input').val('master');
        }
    });

    // Save project
    $('body').on('click', '#save-project-btn', function(e) {
        let project_name = ($('#project-name-input').val() || "").trim();
        let project_url = ($('#project-url-input').val() || "").trim();
        let project_vcs = ($('#project-vcs-select').val() || "").trim();
        let project_branch = ($('#project-branch-input').val() || "").trim();
        let load_initial_tags = $('#project-initial-captions-from-tags').is(':checked');
        let project_is_public = $('#set-project-public').is(':checked');
        let project_url_active = $('#project-url-active').is(':checked');

        // Clear errors
        $('.is-invalid').removeClass('is-invalid');

        // Validate fields
        let has_errors = false;
        if (project_name == "") {
            has_errors = true;
            $('#project-name-input').addClass('is-invalid');
        }
        if (project_url != "" && !project_url.indexOf('http') == 0) {
            has_errors = true;
            $('#project-url-input').addClass('is-invalid');
        }
        if (project_url == "") {
            project_url_active = false;
        }
        if (project_vcs == "") {
            has_errors = true;
            $('#project-vcs-select').addClass('is-invalid');
        }
        if (project_branch == "" || project_branch.indexOf(' ') > -1) {
            has_errors = true;
            $('#project-branch-input').addClass('is-invalid');
        }
        if (has_errors) {
            return false;
        }

        let post_data = {
            'name': project_name,
            'project_url': project_url,
            'project_url_active': project_url_active,
            'project_vcs': project_vcs,
            'project_branch': project_branch,
            'is_public': project_is_public,
        };
        if (project_url_active && load_initial_tags) {
            post_data['load_captions_from_tags'] = true;
        }
        $('#new-project-errors').text('');
        $('#save-project-btn').attr({disabled: true})
                              .prepend('<i class="fa fa-spin fa-spinner"></i>');
        $.ajax({
            url: "/api/v1/projects/",
            method: 'POST',
            data: JSON.stringify(post_data),
            contentType: "application/json",
            dataType: "json",
            beforeSend: function(xhr) {
                // Attach CSRF Token
                xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
            },
            success: function(data, textStatus, xhr) {
                // TODO show success message
                // Redirect to new project page
                window.location = '/projects/'+data.id+'/';
            },
            error: function(xhr, textStatus, err) {
                // Error
                console.log("Save error: "+err, xhr);
                $('#save-project-btn').attr({disabled: false}).find('i.fa.fa-spin').remove();
                // Show error message
                if (xhr.responseJSON) {
                    for (let key in xhr.responseJSON) {
                        $('#new-project-errors').text(xhr.responseJSON[key]);
                    }
                }
            }
        });
    });
    $('span[data-toggle="popover"]').popover();
};
