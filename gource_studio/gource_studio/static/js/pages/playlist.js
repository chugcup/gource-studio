"use strict";

// Import globals setup
window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.playlist = {};


/**
 * User Playlist page
 */
App.pages.playlist.init = function(playlist_id, playlist_url, page_options) {
    // Initialize page defaults
    this.playlist_id = playlist_id;
    this.playlist_url = playlist_url;
    page_options = page_options || {};
    this.can_user_edit = !!page_options.can_user_edit;
    this.initial_index = page_options.initial_index || 0;
    this.playlist_contents = page_options.playlist_contents || [];

    // Mutable index counter
    this.current_index = this.initial_index;

    const play_video_at_index = this.play_video_at_index = function(index, options) {
        options = options || {};
        if (options.delay === undefined) {
            options.delay = 0;
        }
        if (options.autoplay === undefined) {
            options.autoplay = true;
        }
        if (!options.force && index === App.pages.playlist.current_index) {
            return false;
        }
        else if (index < 0 || index >= App.pages.playlist.playlist_contents.length) {
            console.log("Index "+index+" outside playlist length");
            return false;
        }
        let video_player = document.getElementById('playlist-video-player');
        let next_video = App.pages.playlist.playlist_contents[index];
        if (next_video.content_url === null) {
            // No video
            console.log("No 'content_url' found for project (index="+index+"): ", next_video);
            $('.project-video-empty').show();
            video_player.children[0].src = "";
            video_player.removeAttribute('poster');
        } else {
            // Set video source/poster
            $('.project-video-empty').hide();
            video_player.children[0].src = next_video.content_url;
            if (next_video.screenshot_url) {
                video_player.poster = next_video.screenshot_url;
            } else {
                video_player.removeAttribute('poster');
            }
        }
        video_player.load();
        // Update index value
        App.pages.playlist.current_index = index;
        // Update URL state
        const url = new URL(window.location);
        if (url.searchParams.get('index') === null && index === 0) {
            url.searchParams.set('index', index);
            window.history.replaceState({index: index}, '', url);  // Unset (implies page 0)
        } else if (url.searchParams.get('index') != ""+index) {
            url.searchParams.set('index', index);
            window.history.pushState({index: index}, '', url);
        }

        // Update title and prev/next links
        update_video_links(index);

        if (options.autoplay && next_video.content_url !== null) {
            setTimeout(function() {
                video_player.play();
            }, options.delay);  // Short delay before starting next video
        }
        return next_video;
    };

    // Play next video in playlist; wrap back to first video
    const play_next_video = this.play_next_video = function(timeout) {
        timeout = timeout || 3000;  // Short delay before moving to next video

        if (App.pages.playlist.current_index < App.pages.playlist.playlist_contents.length-1) {
            setTimeout(function() {
                let next_video = play_video_at_index(App.pages.playlist.current_index+1, {delay: 1000});
                if (next_video.content_url === null && App.pages.playlist.playlist_contents.length > 1) {
                    play_next_video();
                }
            }, timeout);
        } else {
            // Redirect to first video
            // TODO: make setting
            setTimeout(function() {
                let next_video = play_video_at_index(0, {delay: 1000});
                if (next_video.content_url === null && App.pages.playlist.playlist_contents.length > 1) {
                    play_next_video();
                }
            }, timeout);
        }
    };

    // Update the current video title and prev/next buttons
    const update_video_links = this.update_video_links = function(index) {
        if (index < 0 || index >= App.pages.playlist.playlist_contents.length) {
            console.log("Index "+index+" outside playlist length");
            return false;
        }

        // Update current title
        let next_video = App.pages.playlist.playlist_contents[index];
        let $playlist_title = $('#current-playlist-title');
        $playlist_title.html(
          $('<a class="playlist-project-link-btn btn btn-link" href="/projects/'+next_video.project_id+'/" title="View project details"></a>').text(next_video.name)
        );
        // Update document title
        document.title = 'Playlist - '+next_video.name+' - Gource Studio';

        // Update prev/next links
        if (App.pages.playlist.playlist_contents.length <= 1) {
            $('#playlist-prev-container').text('');
            $('#playlist-next-container').text('');
            return;
        }
        if (index > 0) {
            $('#playlist-prev-container').html(
                $('<a href="/playlists/'+App.pages.playlist.playlist_id+'/?index='+(index-1)+'"></a>').text(App.pages.playlist.playlist_contents[index-1].name)
            );
        } else {
            $('#playlist-prev-container').text('');
        }
        if (index < App.pages.playlist.playlist_contents.length-1) {
            $('#playlist-next-container').html(
                $('<a href="/playlists/'+App.pages.playlist.playlist_id+'/?index='+(index+1)+'"></a>').text(App.pages.playlist.playlist_contents[index+1].name)
            );
        } else {
            $('#playlist-next-container').text('');
        }
    };

    $('[data-toggle="tooltip"]').tooltip();
    let video_player = document.getElementById('playlist-video-player');
    video_player.addEventListener('ended', function(e) {
        if (!e) {
            e = window.event;
        }
        // TODO: shuffle (random) mode
        play_next_video();
    }, false);
    window.addEventListener('popstate', function(e) {
        console.log('popstate: ',e.state)
        if (e.state && !isNaN(e.state.index)
                && _.isNumber(e.state.index)
                && e.state.index !== App.pages.playlist.current_index) {
            play_video_at_index(e.state.index);
        }
        else if (e.state === null) {
            const url = new URL(window.location);
            // Should return 'null' if not set
            let url_index = url.searchParams.get('index');
            url_index = (url_index === null) ? 0 : parseInt(url_index);
            if (!isNaN(url_index) && _.isNumber(url_index) && url_index !== App.pages.playlist.current_index) {
                play_video_at_index(url_index);
            }
        }
    });

    update_video_links(App.pages.playlist.current_index);
};
