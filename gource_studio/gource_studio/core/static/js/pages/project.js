"use strict";

// Import globals setup
window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.project = {};


/**
 * Project page (view and edit)
 */
App.pages.project.init = function(project_id, page_options) {
    // Initialize page defaults
    this.project_id = project_id;
    page_options = page_options || {};
    this.user = page_options.user || {};
    this.user_role = page_options.user_role;
    this.can_user_edit = !!page_options.can_user_edit;
    this.is_latest_build = !!page_options.is_latest_build;
    this.is_readonly = !!page_options.is_readonly;
    this.load_id = (+new Date());   // For cache busting

    // Button to copy URL to clipboard
    // - Copies content of previous <input> sibling of parent <div>
    $('body').on('click', '.copy-clipboard-url', function(e) {
        let $input = $(e.currentTarget).parent().prev('input');
        if (!$input.length) { return; }
        let copyrange = document.createRange();
        copyrange.selectNode($input[0]);
        window.getSelection().addRange(copyrange);
        let message = "";
        try {
            let successful = document.execCommand('copy');
            if (successful) {
                message = "Link copied to clipboard";
            } else {
                message = "Could not copy to clipboard";
            }
        } catch (err) {
            message = "Could not copy to clipboard";
        }
        window.getSelection().removeAllRanges();
        // Flash tooltip
        $(e.currentTarget).tooltip({title: message, trigger: 'manual'}).tooltip('show');
        setTimeout(function() {
            $(e.currentTarget).tooltip('hide');
            setTimeout(function() {
                $(e.currentTarget).tooltip('dispose');
            }, 500);
            $(e.currentTarget).removeAttr('title');
        }, 1500);
    });

    const get_popover_preview_content = function(el) {
        let imgsrc = $(el).data('src');
        if (!imgsrc) {
            return "N/A";
        }

        let img = new Image();
        img.id = "popover-preview-"+(+new Date());
        img.className = "project-image-preview";
        img.onload = function() {
            if (isNaN(img.width) || isNaN(img.height)) {
                return;
            }
            // Append 'WIDTH x HEIGHT' label to preview popover
            $('#'+img.id).parent().after(
                $('<div class="project-image-preview-dimensions">').text(
                    img.width + ' x ' + img.height
                )
            );
        };
        img.src = imgsrc+'?_='+App.pages.project.load_id;
        return '<div><a href="'+imgsrc+'" target="_blank">'
              +   img.outerHTML
              + '</a></div>';

    };
    $('body .popover-preview').popover({
        content: function() {
            return get_popover_preview_content(this);
            let imgsrc = $(this).data('src');
            if (!imgsrc) {
                return "N/A";
            }

            let img = new Image();
            img.id = "popover-preview-"+(+new Date());
            img.className = "project-image-preview";
            img.onload = function() {
                if (isNaN(img.width) || isNaN(img.height)) {
                    return;
                }
                // Append 'WIDTH x HEIGHT' label to preview popover
                $('#'+img.id).parent().after(
                    $('<div class="project-image-preview-dimensions">').text(
                        img.width + ' x ' + img.height
                    )
                );
            };
            img.src = imgsrc+'?_='+App.pages.project.load_id;
            return '<div><a href="'+imgsrc+'" target="_blank">'
                  +   img.outerHTML
                  + '</a></div>';
        },
        html: true,
        placement: 'right',
        trigger: 'hover focus'
    });

    $('body').on('click', '#add-to-playlist-btn', function(e) {
        // Open modal and load list of available playlists
        let $modal = $('#confirm-add-to-playlist-modal').modal();
        // - If additional options loaded, empty them
        $modal.find('.add-to-playlist-modal-additional-options ul').html('');

        $.ajax({
            url: '/api/v1/playlists/?per_page=50&include_project_ids=True',
            success: function(data, textStatus, xhr) {
                // Display list of playlists
                if (data.count === 0) {
                    // Empty
                    $modal.find('.add-to-playlist-modal-options').html(
                        '<div class="text-center"><i class="text-muted">No playlists yet.</i></div>'
                    );
                } else {
                    // Display list of playlists
                    $modal.find('.add-to-playlist-modal-options').text('');
                    let $ul = $('<ul class="playlist-select-options-list"></ul>');
                    _.each(data.results, function(item) {
                        if (item.project_ids && item.project_ids.includes(project_id)) {
                            // Already assigned to playlist; show disabled checkbox
                            $ul.append($(
                                _.template('<li><input type="checkbox" value="" checked="checked" disabled /><label for="playlist-add-id-<%- id %>"><%- name %></label></li>')(item)
                            ));
                        } else {
                            // Show regular checkbox
                            $ul.append($(
                                _.template('<li><input type="checkbox" id="playlist-add-id-<%- id %>" value="<%- id %>" /><label for="playlist-add-id-<%- id %>"><%- name %></label></li>')(item)
                            ));
                        }
                    });
                    $modal.find('.add-to-playlist-modal-options').html($ul);
                }
                $modal.find('.add-new-playlist-region').show();
                // FIXME
                // Bind save event
                $modal.on('click', '.create-playlist-btn', function() {
                    let new_name = $modal.find('input[type="text"]').val();
                    $modal.find('input[type="text"]').removeClass('is-invalid');
                    if (!new_name) {
                        $modal.find('input[type="text"]').addClass('is-invalid');
                        return false;
                    }
                    $.ajax({
                        url: '/api/v1/playlists/',
                        method: 'POST',
                        data: JSON.stringify({"name": new_name}),
                        contentType: "application/json",
                        dataType: "json",
                        beforeSend: function(xhr) {
                            // Attach CSRF Token
                            xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                        },
                        success: function(data, textStatus, xhr) {
                            // Add to auxillary section
                            $modal.find('.add-to-playlist-modal-additional-options ul').html(
                                _.template('<li><input type="checkbox" id="playlist-add-id-<%- id %>" value="<%- id %>" /><label for="playlist-add-id-<%- id %>"><%- name %></label></li>')(data)
                            );
                            $modal.find('input[type="text"]').val('');
                        },
                        error: function(xhr, textStatus, err) {
                            console.log('Error creating new playlist: ', err, xhr);
                        }
                    });
                });
                $modal.on('click', '.confirm-save', function() {
                    let playlist_ids = [];
                    // Locate IDs of playlists to add project (video) to
                    _.each($modal.find('.add-to-playlist-modal-options input[type="checkbox"]:checkbox:checked'), function(elem) {
                        if ($(elem).val()) {
                            playlist_ids.push( parseInt($(elem).val()) );
                        }
                    });

                    _.each($modal.find('.add-to-playlist-modal-additional-options input[type="checkbox"]:checkbox:checked'), function(elem) {
                        playlist_ids.push( parseInt($(elem).val()) );
                    });
                    App.debug && console.log('save clicked:', playlist_ids);
                    if (playlist_ids.length === 0) {
                        $modal.modal('hide');
                        return;     // None selected
                    }
                    _.each(playlist_ids, function(playlist_id) {
                        $.ajax({
                            url: '/api/v1/playlists/'+playlist_id+'/projects/',
                            method: 'POST',
                            data: JSON.stringify({"projects": [project_id]}),
                            contentType: "application/json",
                            dataType: "json",
                            beforeSend: function(xhr) {
                                // Attach CSRF Token
                                xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                            },
                            success: function(data, textStatus, xhr) {
                            },
                            error: function(xhr, textStatus, err) {
                                console.log("[ERROR] Error adding to playlist (ID="+playlist_id+"): ", err);
                            }
                        });
                    });

                    $modal.modal('hide');   // Hide immediately
                });
            },
            error: function(xhr, textStatus, err) {
                console.log('Error loading list of playlists: ', err);
            }
        });
        $modal.on('hidden.bs.modal', function() {
            $modal.find('.add-to-playlist-modal-options').text('');
            $modal.find('.add-new-playlist-region').hide();
            $modal.find('.add-to-playlist-modal-additional-options ul').html('');
        });
    });
    const open_gource_command_options_modal = function(options_list, video_size) {
        // Open modal and display Gource command usage
        let $modal = $('#display-gource-command-modal').modal();
        // Base command + explicit video size (-WxH)
        let command_arguments = ['gource'];
        if (video_size) {
            command_arguments.push('-'+video_size);
        }
        // Build additional command arguments on new lines
        _.each(options_list, function(option, idx) {
            if (option.type == 'bool' && ""+option.value != 'true') {
                return;   // skip
            }
            //                        "gource "
            command_arguments.push('\\\n      ');
            command_arguments.push('--'+option.name);
            if (option.type != 'bool') {
                if ((""+option.value).indexOf(" ") > -1) {
                    command_arguments.push('"'+option.value.replaceAll('"', '\\"')+'"');
                } else {
                    command_arguments.push(option.value);
                }
            }
        });
        let command_text = command_arguments.join(' ');
        $modal.find('#display-gource-command-container').text(command_text);
        $modal.on('hidden.bs.modal', function() {
            $modal.find('#display-gource-command-container').text('');
            $modal.off('click.copy-gource-command');
        });
        $modal.on('click.copy-gource-command', '#copy-gource-command-clipboard-btn', function() {
            let successful = App.utils.copyToClipboard(command_text);
            if (successful) {
                $.notify("Command copied to clipboard.", {className: "success", position: "top right"});
            } else {
                $.notify("Failed to copy to clipboard.", {position: "top right"});
            }
        });
    };
    $('body').on('click', '#project-view-gource-command-btn', function(e) {
        let video_size = $('#project-video-size').val();
        open_gource_command_options_modal(
            App.pages.project.project_settings_container.options_selected,
            video_size
        );
    });
    $('body').on('click', '#build-view-gource-command-btn', function(e) {
        let video_size = $('#build-video-size').text();
        open_gource_command_options_modal(
            App.pages.project.build_settings_container.options_selected,
            video_size
        );
    });

    /**
     * =============================
     * Define components
     * =============================
     */

    // Gource Audio/Video settings container
    Vue.component('project-video-size-option', {
        props: {
            value: String,
            label: String,
            selected: Boolean,
        },
        template: '<option :value="value" :selected="selected">{{ label }}</option>',
    });
    Vue.component('project-audio-video-edit', {
        props: {
            video_size: String,
            build_logo: String,
            build_logo_upload: String,
            build_background: String,
            build_background_upload: String,
            build_audio: String,
            build_audio_name: String,
            build_audio_upload: String,
            show_build_logo_form: Boolean,
            show_build_background_form: Boolean,
            show_build_audio_form: Boolean,
            edit_build_logo: Boolean,
            edit_build_background: Boolean,
            edit_build_audio: Boolean,
            can_edit: Boolean,
            is_current_user: Boolean,
            video_size_options: Array,
        },
        updated: function() {
            $(this.$el).find('.popover-preview').popover({
                content: function() {
                    return get_popover_preview_content(this);
                },
                html: true,
                placement: 'right',
                trigger: 'hover focus'
            });
        },
        methods: {
            onSubmitBuildLogo: function(e) {
                e.preventDefault();
                let $form = $('#project_build_logo_file_form');
                $form.find('.is-invalid').removeClass('is-invalid');    // Clear errors

                // Load value for image
                let image = $form.find('input[name="build_logo"]')[0].files[0];
                if (!image) {
                    $form.find('input[name="build_logo"]').addClass('is-invalid');
                    return false;
                }

                let form_data = new FormData();
                form_data.append('build_logo', image);
                let logo_upload_url = $form.attr('action');
                $form.find('button[type="submit"]').attr({disabled: true});

                $.ajax({
                    url: logo_upload_url,
                    type: 'POST',
                    data: form_data,
                    processData: false,
                    contentType: false,
                    dataType: 'json',
                    headers: {
                        "Accept": "application/json; charset=utf-8",
                    },
                    beforeSend: function(xhr) {
                        // Attach CSRF Token
                        xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                    },
                    success: function(data, textStatus, xhr) {
                        App.debug && console.log("ERROR: Logo upload success: ", data);
                        $.notify("Logo updated successfully.", {className: "success", position: "top right"});
                        // Force reload of image (popover)
                        App.pages.project.load_id = (+new Date());
                        // If created, set `build_logo` value from response
                        try {
                            let _url = new URL(data.build_logo);    // Strip host/port prefix
                            App.pages.project.project_audio_video_container.build_logo = _url.pathname;
                        } catch (err) {
                            App.pages.project.project_audio_video_container.build_logo = data.build_logo;
                        }
                        // Empty/reset upload form
                        $form.find('input[name="build_logo"]')[0].value = null;
                        // Dismiss upload form
                        App.pages.project.project_audio_video_container.show_build_logo_form = true;
                        App.pages.project.project_audio_video_container.edit_build_logo = false;
                    },
                    error: function(xhr, textStatus, err) {
                        console.log("ERROR: Logo upload error: ", err, xhr);
                        let responseText = xhr.responseText;
                        try {
                            responseText = JSON.parse(responseText);
                            if (responseText.detail) {
                                $.notify(responseText.detail, {autoHide: false, position: 'top center'});
                            }
                        } catch (err) {
                            console.log("Error parsing response as JSON: ", err);
                            $.notify("Error occurred while submitting logo", {autoHide: false, position: 'top center'});
                        }
                    },
                    complete: function(xhr, textStatus) {
                        $form.find('button[type="submit"]').attr({disabled: false});
                    }
                });
            },
            onSubmitBuildBackground: function(e) {
                e.preventDefault();
                let $form = $('#project_build_background_file_form');
                $form.find('.is-invalid').removeClass('is-invalid');    // Clear errors

                // Load value for image
                let image = $form.find('input[name="build_background"]')[0].files[0];
                if (!image) {
                    $form.find('input[name="build_background"]').addClass('is-invalid');
                    return false;
                }

                let form_data = new FormData();
                form_data.append('build_background', image);
                let background_upload_url = $form.attr('action');
                $form.find('button[type="submit"]').attr({disabled: true});

                $.ajax({
                    url: background_upload_url,
                    type: 'POST',
                    data: form_data,
                    processData: false,
                    contentType: false,
                    dataType: 'json',
                    headers: {
                        "Accept": "application/json; charset=utf-8",
                    },
                    beforeSend: function(xhr) {
                        // Attach CSRF Token
                        xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                    },
                    success: function(data, textStatus, xhr) {
                        App.debug && console.log("ERROR: Background upload success: ", data);
                        $.notify("Background updated successfully.", {className: "success", position: "top right"});
                        // Force reload of image (popover)
                        App.pages.project.load_id = (+new Date());
                        // If created, set `build_background` value from response
                        try {
                            let _url = new URL(data.build_background);    // Strip host/port prefix
                            App.pages.project.project_audio_video_container.build_background = _url.pathname;
                        } catch (err) {
                            App.pages.project.project_audio_video_container.build_background = data.build_background;
                        }
                        // Empty/reset upload form
                        $form.find('input[name="build_background"]')[0].value = null;
                        // Dismiss upload form
                        App.pages.project.project_audio_video_container.show_build_background_form = true;
                        App.pages.project.project_audio_video_container.edit_build_background = false;
                    },
                    error: function(xhr, textStatus, err) {
                        console.log("ERROR: Background upload error: ", err, xhr);
                        let responseText = xhr.responseText;
                        try {
                            responseText = JSON.parse(responseText);
                            if (responseText.detail) {
                                $.notify(responseText.detail, {autoHide: false, position: 'top center'});
                            }
                        } catch (err) {
                            console.log("Error parsing response as JSON: ", err);
                            $.notify("Error occurred while submitting background", {autoHide: false, position: 'top center'});
                        }
                    },
                    complete: function(xhr, textStatus) {
                        $form.find('button[type="submit"]').attr({disabled: false});
                    }
                });
            },
            onSubmitBuildAudio: function(e) {
                e.preventDefault();
                let $form = $('#project_build_audio_file_form');
                $form.find('.is-invalid').removeClass('is-invalid');    // Clear errors

                // Load value for image
                let audio = $form.find('input[name="build_audio"]')[0].files[0];
                if (!audio) {
                    $form.find('input[name="build_audio"]').addClass('is-invalid');
                    return false;
                }

                let form_data = new FormData();
                form_data.append('build_audio', audio);
                let audio_upload_url = $form.attr('action');
                $form.find('button[type="submit"]').attr({disabled: true});

                $.ajax({
                    url: audio_upload_url,
                    type: 'POST',
                    data: form_data,
                    processData: false,
                    contentType: false,
                    dataType: 'json',
                    headers: {
                        "Accept": "application/json; charset=utf-8",
                    },
                    beforeSend: function(xhr) {
                        // Attach CSRF Token
                        xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                    },
                    success: function(data, textStatus, xhr) {
                        App.debug && console.log("ERROR: Audio upload success: ", data);
                        $.notify("Background music updated successfully.", {className: "success", position: "top right"});
                        // If created, set `build_audio`/`build_audio_name` values from response
                        try {
                            let _url = new URL(data.build_audio);    // Strip host/port prefix
                            App.pages.project.project_audio_video_container.build_audio = _url.pathname;
                        } catch (err) {
                            App.pages.project.project_audio_video_container.build_audio = data.build_audio;
                        }
                        App.pages.project.project_audio_video_container.build_audio_name = data.build_audio_name;
                        // Empty/reset upload form
                        $form.find('input[name="build_audio"]')[0].value = null;
                        // Dismiss upload form
                        App.pages.project.project_audio_video_container.show_build_audio_form = true;
                        App.pages.project.project_audio_video_container.edit_build_audio = false;
                    },
                    error: function(xhr, textStatus, err) {
                        console.log("ERROR: Audio upload error: ", err, xhr);
                        let responseText = xhr.responseText;
                        try {
                            responseText = JSON.parse(responseText);
                            if (responseText.detail) {
                                $.notify(responseText.detail, {autoHide: false, position: 'top center'});
                            }
                        } catch (err) {
                            console.log("Error parsing response as JSON: ", err);
                            $.notify("Error occurred while submitting music", {autoHide: false, position: 'top center'});
                        }
                    },
                    complete: function(xhr, textStatus) {
                        $form.find('button[type="submit"]').attr({disabled: false});
                    }
                });
            },
        },
        template: `
        <div>
          <div class="form-group">
            <label for="project-video-size"><b>Video Size:</b>&nbsp;</label>
            <select id="project-video-size" name="project-video-size" class="form-control form-control-sm">
              <option is="project-video-size-option"
                      v-for="video_option in video_size_options"
                      v-bind="video_option"
                      v-bind:key="video_option.value"
                      v-bind:value="video_option.value"
                      v-bind:label="video_option.value"
                      v-bind:selected="video_option.value == video_size"></option>
            </select>
          </div>
          <div id="project-build-logo-form-group" class="form-group" v-if="show_build_logo_form">
            <label><b>Logo Image:</b></label>
            <div>
              <button id="project-build-logo-preview" class="btn btn-sm btn-default popover-preview" :data-src="build_logo" v-if="build_logo">
                <i class="fa fa-eye"></i>
              </button>
              <button v-if="can_edit && build_logo" v-on:click="$emit('toggle-edit-project-logo', true)" class="btn btn-sm btn-link" :disabled="!edit_build_logo ? false : 'disabled'" role="button"><i class="fa fa-pencil"></i></button>
              <a id="remove-project-logo-btn" class="btn btn-link" title="Delete logo" v-if="can_edit && build_logo"><i class="fa fa-trash"></i></a>
              <form id="project_build_logo_file_form" method="POST" :action="build_logo_upload" class="form-inline" enctype="multipart/form-data" v-on:submit="onSubmitBuildLogo($event)" v-if="can_edit && edit_build_logo">
                  <input id="project_build_logo_file" class="form-control form-control-file form-control-sm" type="file" name="build_logo" style="display:inline-block; width:auto;"/>
                  <button type="submit" class="btn btn-primary btn-sm">Upload</button>
                  <a class="btn btn-link text-danger" title="Cancel logo upload" v-if="can_edit" v-on:click="$emit('toggle-edit-project-logo', false)"><i class="fa fa-times"></i></a>
              </form>
            </div>
          </div>

          <div id="project-build-background-form-group" class="form-group" v-if="show_build_background_form">
            <label><b>Background Image:</b></label>
            <div>
              <button id="project-build-background-preview" class="btn btn-sm btn-default popover-preview" :data-src="build_background" v-if="build_background">
                <i class="fa fa-eye"></i>
              </button>
              <button v-if="can_edit && build_background" v-on:click="$emit('toggle-edit-project-background', true)" class="btn btn-sm btn-link" :disabled="!edit_build_background ? false : 'disabled'" role="button"><i class="fa fa-pencil"></i></button>
              <a id="remove-project-background-btn" class="btn btn-link" title="Delete background" v-if="can_edit && build_background"><i class="fa fa-trash"></i></a>
              <form id="project_build_background_file_form" method="POST" :action="build_background_upload" class="form-inline" enctype="multipart/form-data" v-on:submit="onSubmitBuildBackground($event)" v-if="can_edit && edit_build_background">
                  <input id="project_build_background_file" class="form-control form-control-file form-control-sm" type="file" name="build_background" style="display:inline-block; width:auto;"/>
                  <button type="submit" class="btn btn-primary btn-sm">Upload</button>
                  <a class="btn btn-link text-danger" title="Cancel background image upload" v-if="can_edit" v-on:click="$emit('toggle-edit-project-background', false)"><i class="fa fa-times"></i></a>
              </form>
            </div>
          </div>

          <div id="project-build-audio-form-group" class="form-group" v-if="show_build_audio_form">
            <label><b>Background Music:</b></label>
            <div>
              <a :href="build_audio" target="_blank" v-if="build_audio && build_audio_name">{{ build_audio_name }}</a>
              <a :href="build_audio" target="_blank" v-if="build_audio && !build_audio_name">Audio File</a>
              <button v-if="can_edit && build_audio" v-on:click="$emit('toggle-edit-project-audio', true)" class="btn btn-sm btn-link" :disabled="!edit_build_audio ? false : 'disabled'" role="button" title="Edit background music file"><i class="fa fa-pencil"></i></button>
              <a id="remove-project-build-audio-btn" class="btn btn-link" :data-filename="build_audio_name" title="Delete background music" v-if="can_edit && build_audio"><i class="fa fa-trash"></i></a>
              <form id="project_build_audio_file_form" method="POST" :action="build_audio_upload" class="form-inline" enctype="multipart/form-data" v-on:submit="onSubmitBuildAudio($event)" v-if="can_edit && edit_build_audio">
                  <input id="project_build_audio_file" class="form-control form-control-file form-control-sm" type="file" name="build_audio" style="display:inline-block; width:auto;"/>
                  <button type="submit" class="btn btn-primary btn-sm">Upload</button>
                  <a class="btn btn-link text-danger" title="Cancel background music upload" v-if="can_edit" v-on:click="$emit('toggle-edit-project-audio', false)"><i class="fa fa-times"></i></a>
              </form>
            </div>
          </div>

          <div class="build-audio-video-actions" v-if="can_edit">
            <button id="add-project-logo-btn" class="btn btn-sm btn-primary" v-if="!show_build_logo_form" v-on:click="$emit('toggle-show-project-logo-form', true)" role="button"><i class="fa fa-rebel"></i> Add Logo</button>
            <button id="add-project-background-btn" class="btn btn-sm btn-primary" v-if="!show_build_background_form" v-on:click="$emit('toggle-show-project-background-form', true)" role="button"><i class="fa fa-picture-o"></i> Add Background</button>
            <button id="add-project-audio-btn" class="btn btn-sm btn-primary" v-if="!show_build_audio_form" v-on:click="$emit('toggle-show-project-audio-form', true)" role="button"><i class="fa fa-music"></i> Add Music</button>
          </div>
        </div>`
    });

    // Gource options (edit/view)
    let GourceOptionMixin = {
        props: {
            name: String,
            label: String,
            value: [String, Number, Boolean],
            value_default: [String, Number, Boolean],
            value_default_set: Boolean,
            type: String,
            placeholder: String,
            description: String,
            description_help: String,
            popover_id: String,
            can_edit: Boolean
        },
        template: `
          <div class="form-group form-inline gource-option-container">
            <div class="gource-option-label" :title="name">
              <b>{{ label }}:</b>
            </div>
            <div class="gource-option-value">
              <div class="gource-option-value-input" v-if="type != 'bool'">
                <input class="form-control form-control-sm" :name="name" type="text" :value="value" v-on:input="$emit('input:value', $event.target.value)" v-on:change="$emit('change:value', $event.target.value)" :placeholder="placeholder" :readonly="!can_edit" />
              </div>
              <div class="gource-option-value-bool" v-if="type == 'bool'">
                <input class="form-control form-control-sm" :name="name" type="text" value="true" :readonly="true" />
              </div>
              <span class="gource-option-info" :id="popover_id"><i class="fa fa-info-circle"></i></span></span>
              <b-popover :target="popover_id" triggers="hover">
                <p class="popover-setting-description">{{ description }}</p>
                <p class="popover-setting-description-help" style="font-size:12px">{{ description_help }}</p>
                <p v-if="value_default_set" class="popover-setting-default"><b>Default:</b> {{ value_default }}</p>
              </b-popover>
              <span class="gource-option-remove text-danger" v-if="can_edit" v-on:click="$emit('remove-gource-option')" title="Delete this setting"><i class="fa fa-times"></i></span>
            </div>
          </div>
        `
    };

    Vue.component('gource-option-edit', {
        mixins: [GourceOptionMixin]
    });
    Vue.component('gource-option-view', {
        mixins: [GourceOptionMixin],
        created: function() {
            this.can_edit = false;
        }
    });

    Vue.component('gource-option-select', {
        props: {
            name: String,
            label: String,
            value_default: [String, Number, Boolean],
            value_default_set: Boolean,
            type: String,
            placeholder: String,
            description: String,
            description_help: String,
            popover_id: String,
            can_edit: Boolean
        },
        template: '<option :value="name">{{ label }}</option>'
    });

    // Gource captions (edit/view)
    let BaseCaptionMixin = {
        props: {
            id: [String, Number],
            timestamp: String,
            text: String,
            can_edit: Boolean
        },
        mounted: function() {
            $(this.$el).find('.gource-caption-datetimepicker').datetimepicker({
                format: 'YYYY-MM-DD HH:mm:ss',
            });
        },
        template: `
          <div class="form-group form-inline gource-caption-container" style="display:flex; width:100%;">
            <input type="text" class="form-control form-control-sm gource-caption-datetimepicker" placeholder="YYYY-MM-DD HH:mm:ss" :value="timestamp" v-on:input="$emit('input:timestamp', $event.target.value)" v-on:change="$emit('change:timestamp', $event.target.value)" :readonly="!can_edit" />
            <input type="text" class="form-control form-control-sm gource-caption-text" placeholder="Message" :value="text" v-on:input="$emit('input:text', $event.target.value)" v-on:change="$emit('change:text', $event.target.value)" :readonly="!can_edit" />
            <span class="project-caption-remove text-danger" v-if="can_edit" v-on:click="$emit('remove-caption')" style="padding-left:12px; cursor:pointer;" title="Delete this caption"><i class="fa fa-times"></i></span>
          </div>
        `
    };

    Vue.component('project-caption-edit', {
        mixins: [BaseCaptionMixin]
    });
    Vue.component('project-caption-view', {
        mixins: [BaseCaptionMixin],
        created: function() {
            this.can_edit = false;
        }
    });

    // Project member items
    Vue.component('project-member-edit', {
        props: {
            id: Number,
            username: String,
            first_name: String,
            last_name: String,
            display_name: String,
            role: String,
            role_display: String,
            date_added: String,
            can_edit: Boolean,
            is_current_user: Boolean
        },
        template: `
            <div class="project-member-list-container">
              <span class="project-member-icon">
                <i class="fa fa-star text-primary" v-if="role == 'owner'"></i>
                <i class="fa fa-user" v-if="role != 'owner'"></i>
              </span>
              <input type="text" class="form-control" name="username" autocomplete="off" :value="display_name" readonly />
              <input type="text" class="form-control" :value="role_display" style="width: 180px; display: inline-block" readonly v-if="role == 'owner' || is_current_user" />
              <select name="role" class="form-control" v-on:change="$emit('change:role', $event.target.value)" v-if="role != 'owner' && !is_current_user">
                <option value="viewer" :selected="role == 'viewer'">Viewer</option>
                <option value="developer" :selected="role == 'developer'">Developer</option>
                <option value="maintainer" :selected="role == 'maintainer'">Maintainer</option>
              </select>
              <a id="remove-project-member-btn" class="btn btn-link text-danger" title="Delete member" v-if="role != 'owner' && !is_current_user" v-on:click="$emit('remove-project-member')"><i class="fa fa-times"></i></a>
              <span class="text-muted" v-if="is_current_user">(It's You)</span>
            </div>`
    });

    /**
     * ====================================
     * Prepare Vue elements for all users
     * ====================================
     */

    // Build settings container (readonly)
    this.build_settings_container = new Vue({
        el: '#gource-settings-region-view',
        data: {
            options_selected: [],
            options_available: [],
        },
        methods: {
            loadAvailable: function(available_list) {
                App.debug && console.log('loadAvailable: ',available_list);
                _.each(available_list, function(item) {
                    this.options_available.push(item);
                }, this);
            },
            addOption: function(name, value, skip_duration) {
                App.debug && console.log('addOption', name, value, skip_duration);
                let new_option = _.findWhere(this.options_available, {name: name});
                if (!new_option) {
                    console.log("Invalid option: "+name);
                    return;
                }
                // Set value (if provided)
                if (!_.isUndefined(value) && !_.isNull(value)) {
                    new_option.value = value;
                } else if (new_option.hasOwnProperty('default')) {
                    new_option.value = new_option.default;
                } else {
                    new_option.value = "";
                }
                new_option.can_edit = false;
                new_option.popover_id = "gource-option-view-popover-"+new_option.name;
                new_option.value_default = new_option.default;  // Alias to avoid JS keyword
                new_option.value_default_set = (new_option.value_default !== null && new_option.value_default !== undefined);
                if (new_option.type == 'bool') {
                    new_option.value = true;
                }
                // Add to selected list
                this.options_selected.push(new_option);
                // Remove from available list
                this.options_available = _.filter(this.options_available, function(item) { return item.name != name; });
            },
        }
    });

    // Build captions container (readonly)
    this.build_captions_container = new Vue({
        el: '#build-captions-region',
        data: {
            captions_list: [],
        },
        methods: {
            addOption: function(id, timestamp, text) {
                App.debug && console.log('[Caption] addOption', id, timestamp, text);
                // Add to selected list
                this.captions_list.push({
                    id: id,
                    timestamp: timestamp,
                    text: text,
                    can_edit: false,
                });
            },
            removeOption: function(id) {
                App.debug && console.log('removeOption', id);
                let target_caption = _.findWhere(this.captions_list, {id: id});
                if (!target_caption) {
                    console.log("Invalid caption: "+id);
                    return;
                }
                // Remove from selected list
                this.captions_list = _.filter(this.captions_list, function(item) { return item.id != id; });
            },
            updateTimestamp: function(caption, timestamp) {
                caption.timestamp = timestamp;
            },
            updateText: function(caption, text) {
                caption.text = text;
            },
        },
    });


    /**
     * =============================
     * Set up editable components
     * =============================
     */

    if (!this.can_user_edit) {
        return;
    }

    // Save settings
    // NOTE: Background Music saved separately
    $('body').on('click', '.save-project-settings-btn', function(e) {
        let video_size = $('#project-video-size').val();
        let gource_options = {};
        // Load current Gource options
        $('#gource-settings-region .gource-option-container').each(function(idx, e) {
            let $input = $(e).find('input');
            if ($input.length > 0 && $input.attr('name')) {
                gource_options[$input.attr('name')] = $input.val();
            }
        });

        let post_data = {
            'video_size': video_size,
            'gource_options': gource_options,
            'sync_gource_options': true,
        };
        $('.save-project-settings-btn').attr({disabled: true});
        $.ajax({
            url: "/api/v1/projects/"+project_id+"/",
            method: 'PATCH',
            data: JSON.stringify(post_data),
            contentType: "application/json",
            dataType: "json",
            beforeSend: function(xhr) {
                // Attach CSRF Token
                xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
            },
            success: function(data, textStatus, xhr) {
                $('.save-project-settings-btn').attr({disabled: false})
                                               .prepend('<i class="fa fa-check"></i>');
                $.notify("Options saved successfully.", {className: "success", position: "top right"});
                // If project settings changed, show Build Now button
                if (data.is_project_changed) {
                    $('.project-changed-notice').show();
                }
            },
            error: function(xhr, textStatus, err) {
                // Error
                console.log("Save error: "+err, xhr);
                $('.save-project-settings-btn').attr({disabled: false})
                                               .prepend('<i class="fa fa-times"></i>');
                App.utils.handleErrorXHR(xhr, err);
            },
            complete: function(xhr, textStatus) {
                setTimeout(function() {
                    $('.save-project-settings-btn').attr({disabled: false})
                                                   .find('.fa').remove();
                }, 1500);
            }
        });
    });

    // Save settings from Manage tab (project slug, public, ...)
    $('body').on('click', '.save-project-manage-btn', function(e) {
        $('#project-manage-container input').removeClass('is-invalid');
        let project_name = $('#project-name').val().trim();
        if (project_name === "") {
            $('#project-name').addClass('is-invalid');
            return;
        }

        let project_slug = $('#project-slug').val().trim();
        if (project_slug === "") {
            project_slug = null;
        }
        let project_is_public = $('#project-is-public').is(':checked');
        let patch_data = {
            'name': project_name,
            'project_slug': project_slug,
            'is_public': project_is_public
        };
        $('.save-project-manage-btn').attr({disabled: true});
        $.ajax({
            url: "/api/v1/projects/"+project_id+"/",
            method: 'PATCH',
            data: JSON.stringify(patch_data),
            contentType: "application/json",
            dataType: "json",
            beforeSend: function(xhr) {
                // Attach CSRF Token
                xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
            },
            success: function(data, textStatus, xhr) {
                $('.save-project-manage-btn').attr({disabled: false})
                                               .prepend('<i class="fa fa-check"></i>');
                $.notify("Project saved successfully.", {className: "success", position: "top right"});
            },
            error: function(xhr, textStatus, err) {
                // Error
                console.log("Save error: "+err, xhr);
                $('.save-project-manage-btn').attr({disabled: false})
                                               .prepend('<i class="fa fa-times"></i>');
                App.utils.handleErrorXHR(xhr, err);
            },
            complete: function(xhr, textStatus) {
                setTimeout(function() {
                    $('.save-project-manage-btn').attr({disabled: false})
                                                   .find('.fa').remove();
                }, 1500);
            }
        });
    });

    // Overall container for project video/audio options
    // - Includes logo/background images
    this.project_audio_video_container = new Vue({
        el: '#project-audio-video-settings-region',
        data: {
            video_size: null,
            build_logo: null,
            build_logo_upload: null,
            build_background: null,
            build_background_upload: null,
            build_audio: null,
            build_audio_name: null,
            build_audio_upload: null,
            show_build_logo_form: false,
            show_build_background_form: false,
            show_build_audio_form: false,
            edit_build_logo: false,
            edit_build_background: false,
            edit_build_audio: false,
            can_edit: false,
            is_current_user: false,
            video_size_options: [],
        },
        methods: {
            loadDefaults: function(data) {
                this.build_logo = data.build_logo;
                this.build_logo_upload = data.build_logo_upload;
                this.build_background = data.build_background;
                this.build_background_upload = data.build_background_upload;
                this.build_audio = data.build_audio;
                this.build_audio_name = data.build_audio_name;
                this.build_audio_upload = data.build_audio_upload;
                this.show_build_logo_form = this.build_logo !== null;
                this.show_build_background_form = this.build_background !== null;
                this.show_build_audio_form = this.build_audio !== null;
                this.video_size = data.video_size;
                this.video_size_options = data.video_size_options;
                this.can_edit = !!data.can_edit;
            },
            toggleShowProjectLogoForm: function(value) {
                this.show_build_logo_form = !!value;
                if (this.show_build_logo_form && this.build_logo === null) {
                    this.edit_build_logo = true;
                }
            },
            toggleShowProjectBackgroundForm: function(value) {
                this.show_build_background_form = !!value;
                if (this.show_build_background_form && this.build_background === null) {
                    this.edit_build_background = true;
                }
            },
            toggleShowProjectAudioForm: function(value) {
                this.show_build_audio_form = !!value;
                if (this.show_build_audio_form && this.build_audio === null) {
                    this.edit_build_audio = true;
                }
            },
            toggleEditProjectLogo: function(value) {
                this.edit_build_logo = !!value;
                if (!this.edit_build_logo && this.build_logo === null) {
                    this.show_build_logo_form = false;
                }
            },
            toggleEditProjectBackground: function(value) {
                this.edit_build_background = !!value;
                if (!this.edit_build_background && this.build_background === null) {
                    this.show_build_background_form = false;
                }
            },
            toggleEditProjectAudio: function(value) {
                this.edit_build_audio = !!value;
                if (!this.edit_build_audio && this.build_audio === null) {
                    this.show_build_audio_form = false;
                }
            },
        },
    });

    // Gource settings container (editable)
    this.project_settings_container = new Vue({
        el: '#gource-settings-region',
        data: {
            options_selected: [],
            options_available: [],
        },
        methods: {
            loadAvailable: function(available_list) {
                App.debug && console.log('loadAvailable: ',available_list);
                _.each(available_list, function(item) {
                    this.options_available.push(item);
                }, this);
            },
            addOption: function(name, value, skip_duration) {
                App.debug && console.log('addOption', name, value, skip_duration);
                let new_option = _.findWhere(this.options_available, {name: name});
                if (!new_option) {
                    console.log("Invalid option: "+name);
                    return;
                }
                // Set value (if provided)
                if (!_.isUndefined(value) && !_.isNull(value)) {
                    new_option.value = value;
                } else if (new_option.hasOwnProperty('default')) {
                    new_option.value = new_option.default;
                } else {
                    new_option.value = "";
                }
                new_option.can_edit = !App.pages.project.is_readonly;
                new_option.popover_id = "gource-option-popover-"+new_option.name;
                new_option.value_default = new_option.default;  // Alias to avoid JS keyword
                new_option.value_default_set = (new_option.value_default !== null && new_option.value_default !== undefined);
                if (new_option.type == 'bool') {
                    new_option.value = true;
                }
                // Add to selected list
                this.options_selected.push(new_option);
                // Remove from available list
                this.options_available = _.filter(this.options_available, function(item) { return item.name != name; });
                if (!skip_duration) {
                    refreshGourceDuration(new_option.name);
                }
            },
            removeOption: function(name, skip_duration) {
                App.debug && console.log('removeOption', name, skip_duration);
                let target_option = _.findWhere(this.options_selected, {name: name});
                if (!target_option) {
                    console.log("Invalid option: "+name);
                    return;
                }
                // Remove 'value' property
                delete target_option.value;

                // Remove from selected list
                this.options_selected = _.filter(this.options_selected, function(item) { return item.name != name; });
                // Re-add to available list
                this.options_available.push(target_option);
                // Re-sort according to initial display 'index'
                this.options_available = _.sortBy(this.options_available, 'index');
                if (!skip_duration) {
                    refreshGourceDuration(target_option.name);
                }
            },
            updateValue: function(option, value) {
                option.value = value;
                refreshGourceDuration(option.name);
            },
        },
    });

    // Recalculate estimated video duration based on entered settings
    const refreshGourceDuration = this.refreshGourceDuration = function(changed_field) {
        let VALID_FIELDS = ["seconds-per-day", "auto-skip-seconds"];
        if (!_.isUndefined(changed_field)) {
            if (!VALID_FIELDS.includes(changed_field)) {
                //App.debug && console.log("Unaffected field changed.  Skipping...");
                return;
            }
        }
        let gource_options = {};
        _.each(App.pages.project.project_settings_container.options_selected, function(item) {
            if (VALID_FIELDS.includes(item.name)) {
                gource_options[item.name] = item.value;
            }
        }, this);

        $.ajax({
            url: "/api/v1/projects/"+project_id+"/utils/duration/",
            method: 'GET',
            data: gource_options,
            contentType: "application/json",
            success: function(data, textStatus, xhr) {
                $('#gource-duration-estimate').text(data.duration_str);
            },
            error: function(xhr, textStatus, err) {
                // Error
                console.log("Duration refresh error: "+err, xhr);
                $('#gource-duration-estimate').text('-');
            }
        });
    };

    this.project_members_container = new Vue({
        el: '#project-members-region',
        data: {
            member_users_list: [],
        },
        methods: {
            addMember: function(id, username, role) {
                App.debug && console.log('[Members] addMember', id, username, role);
                let obj;
                if (_.isObject(id)) {
                    obj = id;
                    obj.id = obj.user.id;
                    obj.username = obj.user.username;
                    obj.first_name = obj.user.first_name;
                    obj.last_name = obj.user.last_name;
                } else {
                    obj = {
                        id: id,
                        username: username,
                        role: role,
                    };
                }
                // Implementation of .capitalize()
                obj.role_display = obj.role.charAt(0).toUpperCase() + obj.role.slice(1);
                obj.can_edit = App.pages.project.can_user_edit;
                obj.display_name = this.getDisplayName(obj);
                obj.is_current_user = (obj.username == App.pages.project.user.username);
                this.member_users_list.push(obj);
                this.member_users_list = _.sortBy(this.member_users_list, 'username');
            },
            // Resolve display name
            // - FIRST LAST (USERNAME)
            //   or
            //   USERNAME
            getDisplayName: function(id) {
                let target_member = null;
                if (_.isObject(id)) {
                    target_member = id;
                } else {
                    target_member = _.findWhere(this.member_users_list, {id: id});
                }
                if (!target_member) {
                    console.log("Invalid member: "+id);
                    return '';
                }
                let account_name = _.filter([target_member.first_name, target_member.last_name]).join(" ");
                return _.template('<% if (account_name) { %><%- account_name %> (<%- username %>)<% } else { %><%- username %><% } %>')({
                    account_name: account_name,
                    username: target_member.username,
                });
            },
            changeRole: function(member, value) {
                let patch_url = '/api/v1/projects/'+project_id+'/members/'+member.id+'/';
                let patch_data = {
                    "role": value
                };
                let self = this;
                $.ajax({
                    url: patch_url,
                    method: 'PATCH',
                    data: JSON.stringify(patch_data),
                    contentType: "application/json",
                    dataType: "json",
                    beforeSend: function(xhr) {
                        // Attach CSRF Token
                        xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                    },
                    success: function(data, textStatus, xhr) {
                        $.notify("Member updated successfully.", {className: "success", position: "top right"});
                        // Update in list
                        self.updateRole(member, value);
                    },
                    error: function(xhr, textStatus, err) {
                        // Error
                        App.utils.handleErrorXHR(xhr, err);
                        // FIXME: restore value in DOM?
                    }
                });
            },
            removeMember: function(id) {
                App.debug && console.log('removeMember', id);
                let target_member = _.findWhere(this.member_users_list, {id: id});
                if (!target_member) {
                    console.log("Invalid member: "+id);
                    return;
                }
                let self = this;
                let delete_url = '/api/v1/projects/'+project_id+'/members/'+target_member.id+'/';
                $.ajax({
                    url: delete_url,
                    method: 'DELETE',
                    //data: JSON.stringify(post_data),
                    contentType: "application/json",
                    dataType: "json",
                    beforeSend: function(xhr) {
                        // Attach CSRF Token
                        xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                    },
                    success: function(data, textStatus, xhr) {
                        $.notify("Member removed successfully.", {className: "success", position: "top right"});
                        // Remove from selected list
                        self.member_users_list = _.sortBy(
                            _.filter(self.member_users_list, function(item) { return item.id != target_member.id; }),
                            'username'
                        );
                    },
                    error: function(xhr, textStatus, err) {
                        // Error
                        App.utils.handleErrorXHR(xhr, err);
                    }
                });

            },
            updateRole: function(member, role) {
                member.role = role;
                // Implementation of .capitalize()
                member.role_display = member.role.charAt(0).toUpperCase() + member.role.slice(1);
            },
        },
    });

    $('body').on('click', '#add-gource-option-btn', function(e) {
        let $selector = $('#gource-new-option-selector');
        if ($selector.length === 0 || $selector.val() == "") { return false; }
        let $option = $selector.find('option:selected');
        if ($option.length === 0) { return false; }

        // Pluck from <select> and add to section
        App.pages.project.project_settings_container.addOption($option.val());
    });


    // ---- CAPTIONS
    // ---------------------------------------

    // Project captions container (editable)
    this.project_captions_container = new Vue({
        el: '#project-captions-region',
        data: {
            captions_list: [],
        },
        methods: {
            addOption: function(id, timestamp, text) {
                App.debug && console.log('[Caption] addOption', id, timestamp, text);
                // Add to selected list
                this.captions_list.push({
                    id: id,
                    timestamp: timestamp,
                    text: text,
                    can_edit: App.pages.project.can_user_edit,
                });
            },
            removeOption: function(id) {
                App.debug && console.log('removeOption', id);
                let target_caption = _.findWhere(this.captions_list, {id: id});
                if (!target_caption) {
                    console.log("Invalid caption: "+id);
                    return;
                }
                // Remove from selected list
                this.captions_list = _.filter(this.captions_list, function(item) { return item.id != id; });
            },
            updateTimestamp: function(caption, timestamp) {
                caption.timestamp = timestamp;
            },
            updateText: function(caption, text) {
                caption.text = text;
            },
        },
    });


    $('body').on('click', '.load-captions-from-project-tags-btn', function(e) {
        var post_data = {
            'action': 'load_captions_from_tags',
        };
        $.ajax({
            url: "/api/v1/projects/"+project_id+"/actions/",
            method: 'POST',
            data: JSON.stringify(post_data),
            contentType: "application/json",
            dataType: "json",
            beforeSend: function(xhr) {
                // Attach CSRF Token
                xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
            },
            success: function(data, textStatus, xhr) {
                $.notify("Captions loaded successfully.", {className: "success", position: "top right"});
                setTimeout(function() {
                    window.location.reload();
                }, 2000);
            },
            error: function(xhr, textStatus, err) {
                // Error
                App.utils.handleErrorXHR(xhr, err);
            }
        });
    });

    // Save captions
    $('body').on('click', '.save-project-captions-btn', function(e) {
        let captions_list = [];
        let error_captions = [];
        $('#project-captions-list .gource-caption-container').each(function(idx, container) {
            let caption_dt = $(container).find('.gource-caption-datetimepicker').val();
            //let caption_dt = $(container).find('.gource-caption-datetimepicker').data('DateTimePicker').viewDate();
            let caption_text = $(container).find('.gource-caption-text').val();
            if (!caption_dt && !caption_text) {
                return;     // Skip completely empty
            } else if (!caption_dt || !caption_text) {
                // Mark error
                error_captions.push(container);
                return;
            }
            captions_list.push({
                timestamp: caption_dt,
                text: caption_text,
            });
        });
        if (error_captions.length > 0) {
            _.each(error_captions, function(container) {
                $(container).addClass('form-error');
            });
            return;
        }
        var post_data = {
            captions: captions_list,
            sync_captions: true
        };
        $('.save-project-captions-btn').attr({disabled: true})
                             .find('i.fa').removeClass('fa-tag fa-times fa-check')
                                          .addClass('fa-spinner fa-spin');
        $.ajax({
            url: "/api/v1/projects/"+project_id+"/captions/",
            method: "POST",
            data: JSON.stringify(post_data),
            contentType: "application/json",
            dataType: "json",
            beforeSend: function(xhr) {
                // Attach CSRF Token
                xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
            },
            success: function(data, textStatus, xhr) {
                $('.save-project-captions-btn').attr({disabled: false})
                                 .find('i.fa').removeClass('fa-tag fa-times fa-check fa-spinner fa-spin')
                                              .addClass('fa-check');
                $.notify("Captions saved successfully.", {className: "success", position: "top right"});
            },
            error: function(xhr, textStatus, err) {
                // Error
                $('.save-project-captions-btn').attr({disabled: false})
                                 .find('i.fa').removeClass('fa-tag fa-times fa-check fa-spinner fa-spin')
                                              .addClass('fa-times');
                App.utils.handleErrorXHR(xhr, err);
            }
        });
    });


    let gource_caption_template = _.template(''
      +'<div class="form-group gource-caption-container" style="display:flex; width:100%;">'
      +  '<input type="text" class="form-control form-control-sm gource-caption-datetimepicker" style="width:150px; font-size:12px; line-height:32px;" placeholder="YYYY-MM-DD HH:mm:ss" value="<%- caption_timestamp %>" />'
      +  '<input type="text" class="form-control form-control-sm gource-caption-text" style="width:400px; font-size:12px; line-height:32px;" placeholder="Message" value="<%- caption_text %>" />'
      +'</div>');

    $('body').on('click', '.add-caption-btn', function(e) {
        App.pages.project.project_captions_container.addOption('tmp-'+_.random(0, 999999));
    });


    // Queue build handler
    const queue_project_build = this.queue_project_build = function(options) {
        options = options || {};
        $('body #queue-project-build-modal .error-message').text('');
        return $.ajax({
            url: "/api/v1/projects/"+App.pages.project.project_id+"/builds/new/",
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
                window.location = "/projects/"+App.pages.project.project_id+"/builds/";
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
        if ($('#queue_project_build_remix_audio').is(':checked')) {
            options.remix_audio= true;
        }
        if ($('#queue_project_build_refetch_log').is(':checked')) {
            options.refetch_log = true;
        }
        let $ajax = queue_project_build(options);
    });

    // Logo Image
//    $('body').on('click', '#add-project-logo-btn', function(e) {
//        $('#project-build-logo-form-group').show();
//        $('#add-project-logo-btn').hide();
//    });
    $('body').on('click', '#remove-project-logo-btn', function(e) {
        let delete_url = '/api/v1/projects/'+project_id+'/build_logo/';
        let $form = $('#project_build_logo_file_form');

        // Copy modal template to new element (for modal)
        let $dom = $($('#confirm-delete-file-modal')[0].outerHTML);
        $dom[0].id = 'confirm-delete-build-logo-modal';
        // Set title and main description
        $dom.find('.confirm-delete-file-title').text('Delete Logo?');
        $dom.find('.confirm-delete-object-name').text('this logo');
        // Set image preview
        let imgsrc = $('#project-build-logo-preview').data('src');
        $dom.find('.confirm-delete-file-image').append(
            '<img class="project-image-preview" src="'+imgsrc+'" />'
        );
        $('body').append($dom);

        // Activate modal
        let $modal = $dom.modal();
        $modal.on('hidden.bs.modal', function() {
            $modal.modal('dispose');
            $dom.remove();
        });
        $modal.on('click', '.confirm-delete', function() {
            // Delete entry
            $.ajax({
                url: delete_url,
                method: 'DELETE',
                headers: {
                    "Accept": "application/json; charset=utf-8",
                    "Content-Type": "application/json; charset=utf-8"
                },
                beforeSend: function(xhr) {
                    // Attach CSRF Token
                    xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                },
                success: function(data, textStatus, xhr) {
                    // Dismiss modal
                    $modal.modal('hide');

                    $.notify("Logo removed successfully.", {className: "success", position: "top right"});
                    // Empty `build_logo` values
                    App.pages.project.project_audio_video_container.build_logo = null;
                    App.pages.project.project_audio_video_container.show_build_logo_form = false;
                    App.pages.project.project_audio_video_container.edit_build_logo = false;
                    // Empty/reset upload form
                    $form.find('input[name="build_logo"]').val(null);
                },
                error: function(xhr, textStatus, err) {
                    console.log("ERROR: ",err);
                },
            });
        });
    });

    // Background Image
    $('body').on('click', '#remove-project-background-btn', function(e) {
        let delete_url = '/api/v1/projects/'+project_id+'/build_background/';
        let $form = $('#project_build_background_file_form');

        // Copy modal template to new element (for modal)
        let $dom = $($('#confirm-delete-file-modal')[0].outerHTML);
        $dom[0].id = 'confirm-delete-build-background-modal';
        // Set title and main description
        $dom.find('.confirm-delete-file-title').text('Delete Background?');
        $dom.find('.confirm-delete-object-name').text('this background');
        // Set image preview
        let imgsrc = $('#project-build-background-preview').data('src');
        $dom.find('.confirm-delete-file-image').append(
            '<img class="project-image-preview" src="'+imgsrc+'" />'
        );
        $('body').append($dom);

        // Activate modal
        let $modal = $dom.modal();
        $modal.on('hidden.bs.modal', function() {
            $modal.modal('dispose');
            $dom.remove();
        });
        $modal.on('click', '.confirm-delete', function() {
            // Delete entry
            $.ajax({
                url: delete_url,
                method: 'DELETE',
                headers: {
                    "Accept": "application/json; charset=utf-8",
                    "Content-Type": "application/json; charset=utf-8"
                },
                beforeSend: function(xhr) {
                    // Attach CSRF Token
                    xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                },
                success: function(data, textStatus, xhr) {
                    // Dismiss modal
                    $modal.modal('hide');

                    $.notify("Background image removed successfully.", {className: "success", position: "top right"});
                    // Empty `build_background` values
                    App.pages.project.project_audio_video_container.build_background = null;
                    App.pages.project.project_audio_video_container.show_build_background_form = false;
                    App.pages.project.project_audio_video_container.edit_build_background = false;
                    // Empty/reset upload form
                    $form.find('input[name="build_background"]').val(null);
                },
                error: function(xhr, textStatus, err) {
                    console.log("ERROR: ",err);
                },
            });
        });
    });

    // Background Music
    $('body').on('click', '#remove-project-build-audio-btn', function(e) {
        let delete_url = '/api/v1/projects/'+project_id+'/build_audio/';
        let $form = $('#project_build_audio_file_form');

        // Copy modal template to new element (for modal)
        let $dom = $($('#confirm-delete-file-modal')[0].outerHTML);
        $dom[0].id = 'confirm-delete-build-audio-modal';
        // Set title and main description
        $dom.find('.confirm-delete-file-title').text('Delete Music?');
        $dom.find('.confirm-delete-object-name').text('the background music');
        // Set name
        let filename = $(e.currentTarget).data('filename');
        $dom.find('.confirm-delete-file-name').text(filename ? filename : "");
        $('body').append($dom);

        // Activate modal
        let $modal = $dom.modal();
        $modal.on('hidden.bs.modal', function() {
            $modal.modal('dispose');
            $dom.remove();
        });
        $modal.on('click', '.confirm-delete', function() {
            // Delete entry
            $.ajax({
                url: delete_url,
                method: 'DELETE',
                headers: {
                    "Accept": "application/json; charset=utf-8",
                    "Content-Type": "application/json; charset=utf-8"
                },
                beforeSend: function(xhr) {
                    // Attach CSRF Token
                    xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                },
                success: function(data, textStatus, xhr) {
                    // Dismiss modal
                    $modal.modal('hide');

                    $.notify("Background music removed successfully.", {className: "success", position: "top right"});
                    // Empty `build_audio`/`build_audio_name` values
                    App.pages.project.project_audio_video_container.build_audio = null;
                    App.pages.project.project_audio_video_container.build_audio_name = null;
                    App.pages.project.project_audio_video_container.show_build_audio_form = false;
                    App.pages.project.project_audio_video_container.edit_build_audio = false;
                    // Empty/reset upload form
                    $form.find('input[name="build_audio"]').val(null);
                },
                error: function(xhr, textStatus, err) {
                    console.log("ERROR: ",err);
                },
            });
        });
    });
    $('body').on('click', '#add-new-member-btn', function(e) {
        let new_member_username = $('#new-member-input').val();
        let new_member_role = $('#new-member-role').val();
        if (!new_member_username || !new_member_role) {
            return;
        }

        let post_data = {
            username: new_member_username,
            role: new_member_role,
        };

        $('.add-new-member-btn').attr({disabled: true});
        $.ajax({
            url: "/api/v1/projects/"+project_id+"/members/",
            method: 'POST',
            data: JSON.stringify(post_data),
            contentType: "application/json",
            dataType: "json",
            beforeSend: function(xhr) {
                // Attach CSRF Token
                xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
            },
            success: function(data, textStatus, xhr) {
                $.notify("Member added successfully.", {className: "success", position: "top right"});
                App.pages.project.project_members_container.addMember(data);
                // Reset input
                $('#new-member-input').val('');
                $('#new-member-role').val('viewer');
            },
            error: function(xhr, textStatus, err) {
                // Error
                console.log("Save error: "+err, xhr);
                App.utils.handleErrorXHR(xhr, err);
            },
            complete: function(xhr, textStatus) {
                setTimeout(function() {
                    $('.add-new-member-btn').attr({disabled: false});
                }, 1500);
            }
        });
    });
};
