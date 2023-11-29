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
    this.can_user_edit = !!page_options.can_user_edit;
    this.is_latest_build = !!page_options.is_latest_build;
    this.is_readonly = !!page_options.is_readonly;
    this.load_id = (+new Date());   // For cache busting

    // Save settings
    // NOTE: Background Music saved separately
    $('body').on('click', '.save-project-settings-btn', function(e) {
        let video_size = $('#project-video-size').val();
        let gource_options = {};
        $('.gource-option-container').each(function(idx, e) {
            let $input = $(e).find('input');
            if ($input.length > 0 && $input.attr('name')) {
                gource_options[$input.attr('name')] = $input.val();
            }
        });

        let post_data = {
            'video_size': video_size,
            'gource_options': gource_options
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

    // Gource settings container
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

    // ---- OPTIONS
    // ---------------------------------------

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

    $('body').on('click', '#add-gource-option-btn', function(e) {
        let $selector = $('#gource-new-option-selector');
        if ($selector.length === 0 || $selector.val() == "") { return false; }
        let $option = $selector.find('option:selected');
        if ($option.length === 0) { return false; }

        // Pluck from <select> and add to section
        App.pages.project.project_settings_container.addOption($option.val());
    });

    $('body').on('click', '.edit-audio-file', function(e) {
        $(e.currentTarget).hide();
        $('#project_build_audio_file_form').show();
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


    let BaseCaptionMixin = {
        props: {
            id: [String, Number],
            timestamp: String,
            text: String,
            can_edit: Boolean
        },
        mounted: function() {
            $(this.$el.querySelector('.gource-caption-datetimepicker')).datetimepicker({
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
            captions: captions_list
        };
        $('.save-project-captions-btn').attr({disabled: true})
                             .find('i.fa').removeClass('fa-tag fa-times fa-check')
                                          .addClass('fa-spinner fa-spin');
        $.ajax({
            //url: "/api/v1/projects/"+project_id+"/",
            //method: 'PATCH',
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

    $('body .popover-preview').popover({
        content: function() {
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

    // Logo Image
    $('body').on('click', '#add-project-logo-btn', function(e) {
        $('#project-build-logo-form-group').show();
        $('#add-project-logo-btn').hide();
    });
    $('body').on('click', '#remove-project-logo-btn', function(e) {
        let delete_url = '/api/v1/projects/'+project_id+'/build_logo/';
        // Set title
        $('#confirm-delete-file-modal #confirm-delete-file-title').text('Delete Logo?');
        // Set main description
        $('#confirm-delete-file-modal #confirm-delete-object-name').text('this logo');
        // Set name
        $('#confirm-delete-file-modal #confirm-delete-file-name').text('');
        // Set image preview
        App.debug && console.log('--- ',$(e.currentTarget).parents('.form-group'));
        let imgsrc = $('#project-build-logo-preview').data('src');
        $('#confirm-delete-file-modal #confirm-delete-file-image').append(
            '<img class="project-image-preview" src="'+imgsrc+'" />'
        );
        let $modal = $('#confirm-delete-file-modal').modal();
        $modal.on('click', '.confirm-delete', function() {
            // Delete entry
            $.ajax({
                url: delete_url,
                method: 'DELETE',
                beforeSend: function(xhr) {
                    // Attach CSRF Token
                    xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                },
                success: function(data, textStatus, xhr) {
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
            $('#confirm-delete-file-modal #confirm-delete-file-title').text('Delete File?');
            $('#confirm-delete-file-modal #confirm-delete-object-name').text('this file');
            $('#confirm-delete-file-modal #confirm-delete-file-image').text('');
        });
    });

    // Background Image
    $('body').on('click', '#add-project-background-btn', function(e) {
        $('#project-build-background-form-group').show();
        $('#add-project-background-btn').hide();
    });
    $('body').on('click', '#remove-project-background-btn', function(e) {
        let delete_url = '/api/v1/projects/'+project_id+'/build_background/';
        // Set title
        $('#confirm-delete-file-modal #confirm-delete-file-title').text('Delete Background?');
        // Set main description
        $('#confirm-delete-file-modal #confirm-delete-object-name').text('this background');
        // Set name
        $('#confirm-delete-file-modal #confirm-delete-file-name').text('');
        // Set image preview
        let imgsrc = $('#project-build-background-preview').data('src');
        $('#confirm-delete-file-modal #confirm-delete-file-image').append(
            '<img class="project-image-preview" src="'+imgsrc+'" />'
        );
        let $modal = $('#confirm-delete-file-modal').modal();
        $modal.on('click', '.confirm-delete', function() {
            // Delete entry
            $.ajax({
                url: delete_url,
                method: 'DELETE',
                beforeSend: function(xhr) {
                    // Attach CSRF Token
                    xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                },
                success: function(data, textStatus, xhr) {
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
            $('#confirm-delete-file-modal #confirm-delete-file-title').text('Delete File?');
            $('#confirm-delete-file-modal #confirm-delete-object-name').text('this file');
            $('#confirm-delete-file-modal #confirm-delete-file-image').text('');
        });
    });

    // Background Music
    $('body').on('click', '#add-project-audio-btn', function(e) {
        $('#project-build-audio-form-group').show();
        $('#add-project-audio-btn').hide();
    });
    $('body').on('click', '#remove-project-build-audio-btn', function(e) {
        let delete_url = '/api/v1/projects/'+project_id+'/build_audio/';
        // Set title
        $('#confirm-delete-file-modal #confirm-delete-file-title').text('Delete Music?');
        // Set main description
        $('#confirm-delete-file-modal #confirm-delete-object-name').text('the background music');
        // Set name
        let filename = $(e.currentTarget).data('filename');
        $('#confirm-delete-file-modal #confirm-delete-file-name').text(filename ? filename : "");
        // Set image preview
        $('#confirm-delete-file-modal #confirm-delete-file-image').text('');
        let $modal = $('#confirm-delete-file-modal').modal();
        $modal.on('click', '.confirm-delete', function() {
            // Delete entry
            $.ajax({
                url: delete_url,
                method: 'DELETE',
                beforeSend: function(xhr) {
                    // Attach CSRF Token
                    xhr.setRequestHeader("X-CSRFToken", App.utils.getCookie("csrftoken"));
                },
                success: function(data, textStatus, xhr) {
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
            $('#confirm-delete-file-modal #confirm-delete-file-title').text('Delete File?');
            $('#confirm-delete-file-modal #confirm-delete-object-name').text('this file');
            $('#confirm-delete-file-modal #confirm-delete-file-image').text('');
        });
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
};
