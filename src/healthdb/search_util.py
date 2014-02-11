import re
import string

_PUNCTUATION_REGEX = re.compile(
    '[' + re.escape(string.punctuation.replace('-', '').replace(
        '_', '').replace('#', '').replace('-', '')) + ']')

_PUNCTUATION_SEARCH_REGEX = re.compile(
    '[' + re.escape(string.punctuation.replace('_', '').replace(
        '#', '').replace('-', '')) + ']')

def splitter(text, indexing=False, **kwargs):
    """
    Returns an array of  keywords, that are included
    in query. All character besides letters, numbers, '_', and '-'
    are split characters.

    This is for use with gae-search.
    See also search/core.py default_splitter()
    See also http://gae-full-text-search.appspot.com/docs/SearchIndexProperty/
    
    Examples:
    - text='word1/word2 word3'
      returns ['word1', 'word2', word3]
    - text='word2-word3'
      returns ['word2-word3']
    """
    # This line converts a date value to a string:
    text = "%s" % text

    if not text:
        return []
    if not indexing:
        return _PUNCTUATION_SEARCH_REGEX.sub(u' ', text.lower()).split()
    keywords = []
    for word in set(_PUNCTUATION_REGEX.sub(u' ', text.lower()).split()):
        if word:
            keywords.append(word)
    return keywords
