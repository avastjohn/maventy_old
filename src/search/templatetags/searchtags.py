# -*- coding: utf-8 -*-
from django.conf import settings
from django.template import TemplateSyntaxError, TemplateDoesNotExist
from django.template.loader import get_template
from django.utils.safestring import mark_safe
from itertools import ifilter
from ragendja.template import Library
import re

whitespace = re.compile(r'[\s\-\'\"]+')

register = Library()

@register.filter
def searchexcerpt(text, query, context_words=10, startswith=True):
    if not isinstance(query, (list, tuple, set)):
        query = set(whitespace.split(query))

    query = [re.escape(q) for q in query if q]
    exprs = [re.compile(r"^%s$" % p, re.IGNORECASE) for p in query]
    
    re_template = startswith and r"\b(%s)" or r"\b(%s)\b"
    pieces = re.compile(re_template % "|".join(query), re.IGNORECASE).split(text)
    matches = {}
    word_lists = []
    index = {}
    for i, piece in enumerate(pieces):
        word_lists.append(whitespace.split(piece))
        if i % 2:
            index[i] = expr = ifilter(lambda e: e.match(piece), exprs).next()
            matches.setdefault(expr, []).append(i)
    
    def merge(lists):
        merged = []
        for words in lists:
            if not words:
                continue
            if merged:
                merged[-1] += words[0]
                del words[0]
            merged.extend(words)
        return merged
    
    i = 0
    merged = []
    for j in map(min, matches.itervalues()):
        merged.append(merge(word_lists[i:j]))
        merged.append(word_lists[j])
        i = j + 1
    merged.append(merge(word_lists[i:]))
    
    output = []
    for i, words in enumerate(merged):
        omit = None
        if i == len(merged) - 1:
            omit = slice(max(1, 2 - i) * context_words + 1, None)
        elif i == 0:
            omit = slice(-context_words - 1)
        elif not i % 2:
            omit = slice(context_words + 1, -context_words - 1)
        if omit and words[omit]:
            words[omit] = ["..."]
        output.append(" ".join(words))
    
    return ''.join(output)

@register.filter
def highlightedexcerpt(text, query, context_words=10, startswith=True, class_name='highlight'):
    if not isinstance(query, (list, tuple, set)):
        query = set(whitespace.split(query))
    
    text = searchexcerpt(text, query, context_words=context_words, startswith=startswith)

    query = [re.escape(q) for q in query if q]
    re_template = startswith and r"\b(%s)" or r"\b(%s)\b"
    expr = re.compile(re_template % "|".join(query), re.IGNORECASE)
    template = '<span class="%s">%%s</span>' % class_name
    matches = []
    
    def replace(match):
        matches.append(match)
        return template % match.group(0)

    return mark_safe(expr.sub(replace, text))

@register.context_tag
def global_search_form(context, url, label='Search'):
    request = context['request']
    form_module, xxx, class_name= getattr(settings, 'GLOBAL_SEARCH_FORM',
        'search.forms.SearchForm').rpartition('.')
    form_class = getattr(__import__(form_module, {}, {}, ['']), class_name)
    html = '<form action="%(url)s" method="get">%(input)s<input type="submit" value="%(label)s" /></form>'
    if request.path == url:
        form = form_class(request.GET, auto_id='global_search_%s')
    else:
        form = form_class(auto_id='global_search_%s')
    return html % {'url': url, 'input': form['query'], 'label': label}

@register.context_tag
def load_object_list(context):
    """
    Loads search__object_list for iteration and applies the converter to it.
    """
    name = context['template_object_name'] + '_list'
    object_list = context[name]
    converter = context.get('search__converter')
    if converter:
        object_list = converter(object_list)
    context['search__object_list'] = object_list
    return ''

@register.context_tag
def display_in_list(context, item):
    template_name = '%s/%s_in_list.html' % (
            item._meta.app_label, item._meta.object_name.lower())
    context.push()
    context[ context['template_object_name'] ] = item
    try:
        output = get_template(template_name).render(context)
    except (TemplateSyntaxError, TemplateDoesNotExist), e:
        if settings.TEMPLATE_DEBUG:
            raise
        output = ''
    except:
        output = '' # Fail silently for invalid included templates.
    context.pop()
    return output

@register.filter
def resultsformat(hits, results_format):
    if not hits:
        format = results_format[0]
    elif hits == 1:
        format = results_format[1]
    elif hits <= 300:
        format = results_format[2]
    else:
        format = results_format[3]
        hits -= 1
    return format % {'hits': hits}

@register.inclusion_tag('search/pagenav.html', takes_context=True)
def pagenav(context, adjacent_pages=3):
    """
    To be used in conjunction with the object_list generic view.

    Adds pagination context variables for use in displaying first, adjacent and
    last page links in addition to those created by the object_list generic
    view.

    """
    page = context['page']
    pages = context['pages']
    if page < adjacent_pages:
        page_range = range(1, 2 * adjacent_pages)
    elif pages - page + 1 < adjacent_pages:
        page_range = range(pages - 2 * adjacent_pages + 2, pages + 1)
    else:
        page_range = range(page - adjacent_pages, page + adjacent_pages + 1)
    page_range = [n for n in page_range if n >= 1 and n <= pages]
    if pages not in page_range and pages - 1 in page_range:
        page_range.append(pages)
    if 1 not in page_range and 2 in page_range:
        page_range.insert(0, 1)
    return {
        'hits': context['hits'],
        'results_per_page': context['results_per_page'],
        'page': page,
        'pages': pages,
        'page_range': page_range,
        'next': context['next'],
        'previous': context['previous'],
        'has_next': context['has_next'],
        'has_previous': context['has_previous'],
        'show_first': 1 not in page_range,
        'show_last': pages not in page_range,
        'base_url': context['base_url'],
    }
