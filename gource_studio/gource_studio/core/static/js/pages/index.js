"use strict";

// Import globals setup
window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.index = {};


/**
 * Index (Home) page
 */
App.pages.index.init = function(page_options) {
    // Initialize page defaults
    page_options = page_options || {};
    this.can_user_edit = !!page_options.can_user_edit;
};
