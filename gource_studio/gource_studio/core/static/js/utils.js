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
