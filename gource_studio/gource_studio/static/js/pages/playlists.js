"use strict";

// Import globals setup
window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.playlists = {};


/**
 * User Playlists (list) page
 */
App.pages.playlists.init = function(page_options) {
    // Initialize page defaults
    page_options = page_options || {};

    $('.delete-playlist-btn').on('click', function(e) {
        let playlist_id = $(e.currentTarget).attr('data-playlist-id');
        if (!playlist_id) {
            return;
        }
        let delete_url = '/api/v1/playlists/'+playlist_id+'/';
        // Set name
        let name = $(e.currentTarget).attr('data-name');
        $('#confirm-delete-playlist-modal #confirm-delete-playlist-name').text(name ? name : "N/A");
        let $modal = $('#confirm-delete-playlist-modal').modal();
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
            $('#confirm-delete-playlist-modal #confirm-delete-playlist-name').text('');
        });
    });
};
