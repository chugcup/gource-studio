"use strict";

window.App = window.App || {};
window.App.utils = {};


// https://docs.djangoproject.com/en/dev/ref/csrf/#ajax
// - See also: https://github.com/js-cookie/js-cookie/
App.utils.getCookie = function(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
};


App.utils.handleErrorXHR = function(xhr, err) {
    // TODO fallback on 'responseText'?
    if (xhr.responseJSON) {
        for (let key in xhr.responseJSON) {
            $.notify(xhr.responseJSON[key], {autoHide: false, position: 'top center'});
        }
    } else {
        $.notify(err, {autoHide: false, position: 'top center'});
    }
};


// Simple way to "deep" cloning JSON object
App.utils.cloneJSON = function(data) {
    if (_.isArray(data) || _.isObject(data)) {
        return JSON.parse(
            JSON.stringify(data)
        );
    }
    return data;    // Not really a cloneable object
};

// Helper to copy input text to user's clipboard
App.utils.copyToClipboard = function(data) {
    const el = document.createElement('textarea');
    el.value = data;
    el.setAttribute('readonly', '');
    el.style.position = 'absolute';
    el.style.left = '-9999px';
    document.body.appendChild(el);
    const selected = document.getSelection().rangeCount > 0
                        ? document.getSelection().getRangeAt(0)
                        : false;
    el.select();

    let successful = false;
    try {
        successful = document.execCommand('copy');
    } catch (err) {
        console.log('Unable to copy to clipboard: ', err);
    }
    document.body.removeChild(el);

    if (selected) {
        document.getSelection().removeAllRanges();
        document.getSelection().addRange(selected);
    }
    /*
    let textarea = document.createElement("textarea");
    // Place in the top-left corner of screen regardless of scroll position.
    textarea.style.position = 'fixed';
    textarea.style.top = 0;
    textarea.style.left = 0;
    // Ensure it has a small width and height. Setting to 1px / 1em
    // doesn't work as this gives a negative w/h on some browsers.
    textarea.style.width = '2em';
    textarea.style.height = '2em';
    // We don't need padding, reducing the size if it does flash render.
    textarea.style.padding = 0;
    // Clean up any borders.
    textarea.style.border = 'none';
    textarea.style.outline = 'none';
    textarea.style.boxShadow = 'none';
    // Avoid flash of the white box if rendered for any reason.
    textarea.style.background = 'transparent';

    textarea.value = data;

    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();

    let successful = false;
    try {
        successful = document.execCommand('copy');
        console.log(successful);
    } catch (err) {
        console.log('Unable to copy to clipboard: ', err);
    }
    document.body.removeChild(textarea);
    */
    return successful;
};
