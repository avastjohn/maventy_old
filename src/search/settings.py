from ragendja.settings_post import settings
settings.add_app_media('combined-%(LANGUAGE_CODE)s.js',
    'search/jquery.autocomplete.js',
    'search/autocomplete_activator.js',
    'search/search_forms.js',
)
settings.add_app_media('combined-%(LANGUAGE_DIR)s.css',
    'search/search.css',
    'search/jquery.autocomplete.css',
)
