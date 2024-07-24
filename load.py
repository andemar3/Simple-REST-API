from flask import abort, Blueprint, request
from google.cloud import datastore
import constants
import helpers

client = datastore.Client()

bp = Blueprint('load', __name__, url_prefix='/loads')

# Load properties:
# item
# volume
# weight
# boat


@bp.route('/', methods=['POST', 'GET'])
def load_get_post():
    # create new load
    if request.method == 'POST':
        # check that request content is json and accepts json response
        helpers.check_req_content_is_json(request)
        helpers.check_accepts_json_res(request)
        content = request.get_json()
        # verify the content of the request
        _verify_load_content(content)
        # create new load
        new_load = datastore.entity.Entity(key=client.key(constants.loads))
        new_load = _update_load_content(content, new_load)
        # add boat property
        new_load.update({'boat': None})
        client.put(new_load)
        # return new load with ids and self links
        return helpers.create_response(_add_ids_and_self_links(new_load), 201, constants.json)
    # get list of all loads
    elif request.method == 'GET':
        # check that json response accepts json
        helpers.check_accepts_json_res(request)
        # get limit and offset from request arguments
        q_limit = int(request.args.get('limit', '5'))
        q_offset = int(request.args.get('offset', '0'))
        # get paginated list of loads
        results = helpers.fetch_filtered_and_paginated_list(constants.loads, limit=q_limit, offset=q_offset)
        print(results)
        # add ids and self links
        for load in results.get('loads'):
            load = _add_ids_and_self_links(load)
        return helpers.create_response(results, 200, constants.json)
    else:
        abort(405, description="Method Not Allowed")


@bp.route('/<load_id>', methods=['PATCH', 'PUT', 'DELETE'])
def load_patch_delete(load_id):
    # Edit load
    if request.method == 'PATCH':
        # check that request content is json and accepts json response
        helpers.check_req_content_is_json(request)
        helpers.check_accepts_json_res(request)
        # get load
        load_key = client.key(constants.loads, int(load_id))
        load = client.get(key=load_key)
        # check load exists
        if not load:
            abort(404, description="Load not found")
        # prevent editing if the load is on a load
        if load.get('boat'):
            abort(403, description="Load is on a boat. Remove the load from the boat to edit")
        content = request.get_json()
        # edit and put load
        load = _update_load_content(content, load)
        client.put(load)
        # return edited load with ids and self links
        load = _add_ids_and_self_links(load)
        return helpers.create_response(load, 200, constants.json)
    # Replace load
    elif request.method == 'PUT':
        # check that request content is json and accepts json response
        helpers.check_req_content_is_json(request)
        helpers.check_accepts_json_res(request)
        # get load
        load_key = client.key(constants.loads, int(load_id))
        load = client.get(key=load_key)
        # check load exists
        if not load:
            abort(404, description="Load not found")
        # prevent editing if the load is on a load
        if load.get('boat'):
            abort(403, description="Load is on a boat. Remove the load from the boat to edit")
        content = request.get_json()
        # verify content and replace load
        _verify_load_content(content)
        load = _update_load_content(content, load)
        client.put(load)
        # return replaced load with ids and self links
        load = _add_ids_and_self_links(load)
        return helpers.create_response(load, 201, constants.json)
    elif request.method == 'DELETE':
        # get load
        load_key = client.key(constants.loads, int(load_id))
        load = client.get(key=load_key)
        # check load exists
        if not load:
            abort(404, description="Load not found")
        # prevent deletion if load is on a boat
        if load.get('boat'):
            abort(403, description="Load is on a boat. Remove the load from the boat first")
        # delete load
        client.delete(load_key)
        return helpers.create_response(None, 204, None)
    else:
        abort(405, description="Method Not Allowed")


# update load with its ids and self links
def _add_ids_and_self_links(load):
    load.update({'id': load.id, 'self': request.url_root + constants.loads + '/' + str(load.id)})
    # add self link for boat is load is on a boat
    if load.get('boat'):
        load.update({'boat': {'self': request.url_root + constants.boats + '/' + str(load.get('boat').get('id'))}})
    return load


# verify all load properties are present and valid
def _verify_load_content(content):
    _verify_item(content.get('item'))
    _verify_volume(content.get('volume'))
    _verify_weight(content.get('weight'))


# update load with valid content
def _update_load_content(content, load):
    if content.get('item'):
        _verify_item(content.get('item'))
        load.update({'item': content.get('item')})
    if content.get('volume'):
        _verify_volume(content.get('volume'))
        load.update({'volume': content.get('volume')})
    if content.get('weight'):
        _verify_weight(content.get('weight'))
        load.update({'weight': content.get('weight')})
    return load


# verify item property
def _verify_item(i):
    if not helpers.verify_string(i):
        abort(400, description="At least one required property is invalid or missing")


# verify volume property
def _verify_volume(v):
    if not helpers.verify_pos_int(v):
        abort(400, description="At least one required property is invalid or missing")


# verify weight property
def _verify_weight(w):
    if not helpers.verify_pos_int(w):
        abort(400, description="At least one required property is invalid or missing")
