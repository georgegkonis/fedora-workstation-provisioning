// Portable preferences curated from the Personal profile.
// Edit this file to change settings applied on Firefox startup.

// Startup and interface
user_pref("browser.startup.homepage", "https://start.duckduckgo.com/");
user_pref("browser.toolbars.bookmarks.visibility", "always");
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);
user_pref("sidebar.revamp", true);
user_pref("sidebar.visibility", "hide-sidebar");

// Tracking protection and containers
user_pref("browser.contentblocking.category", "strict");
user_pref("privacy.annotate_channels.strict_list.enabled", true);
user_pref("privacy.bounceTrackingProtection.mode", 1);
user_pref("privacy.fingerprintingProtection", true);
user_pref("privacy.query_stripping.enabled", true);
user_pref("privacy.query_stripping.enabled.pbmode", true);
user_pref("privacy.trackingprotection.consentmanager.skip.pbmode.enabled", false);
user_pref("privacy.trackingprotection.emailtracking.enabled", true);
user_pref("privacy.trackingprotection.enabled", true);
user_pref("privacy.trackingprotection.socialtracking.enabled", true);
user_pref("privacy.userContext.enabled", true);

// Telemetry and recommendations
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("datareporting.usage.uploadEnabled", false);

// AI features and translation
user_pref("browser.ai.control.default", "blocked");
user_pref("browser.ai.control.linkPreviewKeyPoints", "blocked");
user_pref("browser.ai.control.pdfjsAltText", "blocked");
user_pref("browser.ai.control.sidebarChatbot", "blocked");
user_pref("browser.ai.control.smartTabGroups", "blocked");
user_pref("browser.ai.control.smartWindow", "blocked");
user_pref("browser.ai.control.translations", "blocked");
user_pref("browser.ml.chat.enabled", false);
user_pref("browser.ml.chat.page", false);
user_pref("browser.ml.linkPreview.enabled", false);
user_pref("browser.tabs.groups.smart.enabled", false);
user_pref("browser.tabs.groups.smart.userEnabled", false);
user_pref("browser.translations.enable", false);
user_pref("extensions.ml.enabled", false);

// Passwords and payment autofill
user_pref("signon.rememberSignons", false);
user_pref("extensions.formautofill.creditCards.enabled", false);

// Speculative connections
user_pref("network.dns.disablePrefetch", true);
user_pref("network.http.speculative-parallel-limit", 0);
user_pref("network.prefetch-next", false);

// Password manager integration
user_pref("signon.autofillForms", false);
user_pref("signon.generation.enabled", false);
user_pref("signon.management.page.breach-alerts.enabled", false);
