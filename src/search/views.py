# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.paginator import Paginator, InvalidPage
from django.db import models
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.template.defaultfilters import force_escape
from django.utils.translation import ugettext_lazy as _
from ragendja.template import JSONResponse, render_to_response
from search.forms import SearchForm
from search.core import paginated_query
import base64
import cPickle as pickle

default_results_format = (
    _('No results found'),
    _('One result found'),
    _('%(hits)s results found'),
    _('More than %(hits)s results found'),
)

default_title = _('Search')

def update_relation_index(request):
    if 'property_name' in request.POST and 'model_descriptor' in request.POST \
          and 'parent_key' in request.POST and 'delete' in request.POST:
        model_descriptor = pickle.loads(base64.b64decode(request.POST[
            'model_descriptor']))
        model = models.get_model(model_descriptor[0], model_descriptor[1])
        update_property = getattr(model, request.POST['property_name'])
        parent_key = pickle.loads(base64.b64decode(request.POST['parent_key']))
        delete = pickle.loads(base64.b64decode(request.POST['delete']))
        update_property.update_relation_index(parent_key, delete)
    return HttpResponse()

def update_values_index(request):
    if 'property_name' in request.POST and 'model_descriptor' in request.POST \
            and 'old_values' in request.POST and 'new_values' in request.POST:
        model_descriptor = pickle.loads(base64.b64decode(request.POST[
            'model_descriptor']))
        model = models.get_model(model_descriptor[0], model_descriptor[1])
        update_property = getattr(model, request.POST['property_name'])
        values = [pickle.loads(base64.b64decode(request.POST[
            value + '_values'])) for value in ('old', 'new', )]
        update_property.update_values_index(values[1], values[0])
    return HttpResponse()

def query_param_search(request, model, index,
                       filters=(), chain_sort=(), query_converter=None,
                       force_query = False):
    '''Query the data store based on the query request parameter.'''
    query = request.GET.get('query', '').strip()
    results = None
    if query or force_query:
      language = getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE)
      results = getattr(model, index).search(query, filters,
          language=language, chain_sort=chain_sort)
      if query_converter:
          results = query_converter(request, results)
    return results, query

def show_search_results(request, model, index, filters=(), chain_sort=(),
        ignore_params=(), query_converter=None,
        converter=None, search_title=default_title,
        force_results_count=True, results_count_format=default_results_format,
        search_form_class=SearchForm, paginate_by=10, template_name=None,
        template_object_name=None, extra_context={},
        key_based_on_empty_query=False, key_based_order=()):
    """
    Performs a search in model and prints the results.
    For further information see
    search.core.SearchIndexProperty.search()
    """
    results, query = query_param_search(request, model, index,
                                        filters=filters,
                                        chain_sort=chain_sort,
                                        query_converter=query_converter)
    data = { 'query': query }
    data.update(extra_context)

    return show_search_results_from_results(results,
        request, model, index,
        extra_context=data,
        # pass the rest of the parameters through
        filters=filters,
        chain_sort=chain_sort,
        ignore_params=ignore_params,
        converter=converter,
        search_title=search_title,
        force_results_count=force_results_count,
        results_count_format=results_count_format,
        search_form_class=search_form_class,
        paginate_by=paginate_by,
        template_name=template_name,
        template_object_name=template_object_name,
        key_based_on_empty_query=key_based_on_empty_query,
        key_based_order=key_based_order)

def show_search_results_from_results(results,
        request, model, index, filters=(), chain_sort=(),
        ignore_params=(),
        converter=None, search_title=default_title,
        force_results_count=True, results_count_format=default_results_format,
        search_form_class=SearchForm, paginate_by=10, template_name=None,
        template_object_name=None, extra_context={},
        key_based_on_empty_query=False, key_based_order=()):
    """
    Performs a search in model and prints the results.
    For further information see
    search.core.SearchIndexProperty.search()
    """
    if key_based_on_empty_query and not results:
        return key_paginated_object_list(request, model, filters=filters,
            order=key_based_order, search_title=search_title,
            template_name=template_name,
            template_object_name=template_object_name,
            ignore_params=tuple(ignore_params) + ('query',),
            converter=converter,
            paginate_by=paginate_by, search_form_class=search_form_class,
            extra_context=extra_context)

    if not search_form_class:
        search_form = None
    else:
        search_form = search_form_class(request.GET)
        search_form.is_valid()

    if not template_object_name:
        template_object_name = model._meta.object_name.lower()
    data = {
        'force_results_count': force_results_count,
        'search_form': search_form,
        'search_title': search_title,
    }
    data.update(extra_context)
    if not template_name:
        template_name = ('%s/%s_search.html' % (model._meta.app_label,
                                                model._meta.object_name.lower()),
                         'search/search.html')
    
    return paginated_object_list(request, queryset=results, converter=converter,
        paginate_by=paginate_by, template_name=template_name,
        extra_context=data, template_object_name=template_object_name,
        results_count_format=results_count_format, ignore_params=ignore_params)

def _prepare_params(request, ignore_params=()):
    page = request.GET.get('page')
    parameters = request.GET.copy()
    if 'page' in parameters:
        del parameters['page']
    paramstr = parameters.urlencode()
    if paramstr:
        paramstr = paramstr + '&'
    original_base_url = request.path + '?' + paramstr + 'page='
    for param in ignore_params:
        if param in parameters:
            del parameters[param]
    paramstr = parameters.urlencode()
    if paramstr:
        paramstr = paramstr + '&'
    return page, original_base_url, {'base_url': request.path + '?' + paramstr + 'page='}

def paginated_object_list(request, queryset, converter=None, paginate_by=10,
        template_name=None, extra_context={}, template_object_name=None,
        results_count_format=default_results_format, ignore_params=()):
    page, original_base_url, data = _prepare_params(request, ignore_params)
    if not page:
        page = 1
    data.update({
        'template_object_name': template_object_name,
        'force_results_count': True,
        'results_count_format': results_count_format,
        'search__converter': converter,
    })

    paginator = Paginator(queryset, paginate_by, allow_empty_first_page=True)
    try:
        page_number = int(page)
    except ValueError:
        if page == 'last':
            page_number = paginator.num_pages
        else:
            # Page is not 'last', nor can it be converted to an int.
            raise Http404
    try:
        page_obj = paginator.page(page_number)
    except InvalidPage:
        return HttpResponseRedirect(original_base_url + 'last')
    data.update({
        '%s_list' % template_object_name: page_obj.object_list,
        'paginator': paginator,
        'page_obj': page_obj,

        # Legacy template context stuff. New templates should use page_obj
        # to access this instead.
        'is_paginated': page_obj.has_other_pages(),
        'results_per_page': paginator.per_page,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'page': page_obj.number,
        'next': page_obj.next_page_number(),
        'previous': page_obj.previous_page_number(),
        'first_on_page': page_obj.start_index(),
        'last_on_page': page_obj.end_index(),
        'pages': paginator.num_pages,
        'hits': paginator.count,
        'page_range': paginator.page_range,
    })
    for key, value in extra_context.items():
        if callable(value):
            data[key] = value()
        else:
            data[key] = value
    return render_to_response(request, template_name, data)

def live_search_results(request, model, index, filters=(), chain_sort=(),
        limit=30, result_item_formatting=None, query_converter=None,
        converter=None, redirect=False):
    """
    Performs a search in searched_model and prints the results as
    text, so it can be used by auto-complete scripts. 

    limit indicates the number of results to be returned.

    A JSON file is sent to the browser. It contains a list of 
    objects that are created by the function indicated by 
    the parameter result_item_formatting. It is executed for every result
    item.
    Example:
    result_item_formatting=lambda course: {
        'value': course.name + '<br />Prof: ' + course.prof.name,
        'result': course.name + ' ' + course.prof.name,
        'data': redirect=='redirect' and
            {'link': course.get_absolute_url()} or {},
    }
    """
    query = request.GET.get('query', '')
    try:
        limit_override = int(request.GET.get('limit', limit))
        if limit_override < limit:
            limit = limit_override
    except:
        pass
    index_property = getattr(model, index)
    language = getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE)
    results = index_property.search(query, filters, chain_sort=chain_sort,
                                    language=language)
    if query_converter:
        results = query_converter(request, results)
    results = results[:limit]
    if converter:
        results = converter(results)
    data = []
    for item in results:
        if result_item_formatting:
            entry = result_item_formatting(item)
        else:
            value = getattr(item, index_property.properties[0])
            entry = {'value': force_escape(value), 'result': value}
        if 'data' not in entry:
            entry['data'] = {}
        if redirect:
            if 'link' not in entry['data']:
                entry['data']['link'] = item.get_absolute_url()
        data.append(entry)
    return JSONResponse(data)

def key_paginated_object_list(request, model, filters=(), order=(),
        ignore_params=(), converter=None,
        search_title=default_title, paginate_by=10,
        search_form_class=None, template_name=None, template_object_name=None,
        extra_context={}):
    """
    Browse entities using key-based pagination.
    """
    if not search_form_class:
        search_form = None
    else:
        search_form = search_form_class(request.GET)
        search_form.is_valid()

    bookmark, original_base_url, data = _prepare_params(request, ignore_params)
    items, prev, next = paginated_query(model, filters=filters, order=order,
                                        count=paginate_by, bookmark=bookmark)

    if not template_object_name:
        template_object_name = model._meta.object_name.lower()

    data.update({
        template_object_name + '_list': items,
        'template_object_name': template_object_name,
        'has_previous': bool(prev),
        'previous': prev,
        'has_next': bool(next),
        'next': next,
        'page_range': (),
        'show_key_pagenav': True,
        'search_form': search_form,
        'search_title': search_title,
        'query': '',
        'search__converter': converter,
    })
    if not items and not prev and not next:
        data['force_results_count'] = True
    if 'results_count_format' not in extra_context:
        data['results_count_format'] = default_results_format
    for key, value in extra_context.items():
        if callable(value):
            data[key] = value()
        else:
            data[key] = value
    if not template_name:
        name_data = (model._meta.app_label, model._meta.object_name.lower())
        template_name = ('%s/%s_paginated.html' % name_data,
                         '%s/%s_search.html' % name_data,
                         'search/search.html')
    return render_to_response(request, template_name, data)
