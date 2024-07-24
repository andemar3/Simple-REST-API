from flask import abort, Blueprint, request
from google.cloud import datastore
import constants
import helpers

client = datastore.Client()

bp = Blueprint('boat', __name__, url_prefix='/boats')

# Boat properties
# name
# type
# length


@bp.route('', methods=['POST', 'GET'])
def boat_get_post():
    # create new boat
    if request.method == 'POST':
        # check that request content is json and accepts json response
        helpers.check_req_content_is_json(request)
        helpers.check_accepts_json_res(request)
        token = helpers.verify_jwt(request)
        content = request.get_json()
        # verify the content of the request
        _verify_boat_content(content)
        # create boat
        new_boat = datastore.entity.Entity(key=client.key(constants.boats))
        new_boat = _update_boat_content(content, new_boat)
        # add loads and owner properties
        new_boat = helpers.add_owner(new_boat, token.get('sub'))
        new_boat.update({'loads': []})
        client.put(new_boat)
        # return new boat with ids and self links
        return helpers.create_response(_add_ids_and_self_links(new_boat), 201, constants.json)
    # get list of all boats
    elif request.method == 'GET':
        # check that json response is accepted
        helpers.check_accepts_json_res(request)
        # verify jwt and get limit and offset from args
        token = helpers.verify_jwt(request)
        q_limit = int(request.args.get('limit', str(constants.MAX_LIMIT)))
        q_offset = int(request.args.get('offset', '0'))
        user_id = helpers.get_user_id_from_sub(token.get('sub'))
        # get paginated list of all boats belonging to the user
        results = helpers.fetch_filtered_and_paginated_list(constants.boats, limit=q_limit, offset=q_offset,
                                                            filter=('owner', '=', user_id))
        # add ids and self links
        for boat in results.get('boats'):
            boat = _add_ids_and_self_links(boat)
        return helpers.create_response(results, 200, constants.json)
    else:
        abort(405, description="Method Not Allowed")


@bp.route('/<boat_id>', methods=['PATCH', 'PUT', 'DELETE'])
def boat_patch_delete(boat_id):
    # Edit boat
    if request.method == 'PATCH':
        # check that request content is json and accepts json response
        helpers.check_req_content_is_json(request)
        helpers.check_accepts_json_res(request)
        # verify jwt and get boat
        token = helpers.verify_jwt(request)
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        # check boat exists
        if not boat:
            abort(404, description="Load not found")
        # check that boat belongs to the user
        helpers.check_auth(boat.get('owner'), token.get('sub'))
        content = request.get_json()
        # edit and put boat
        boat = _update_boat_content(content, boat)
        client.put(boat)
        # return edited boat with ids and self links
        boat = _add_ids_and_self_links(boat)
        return helpers.create_response(boat, 200, constants.json)
    # Replace boat
    elif request.method == 'PUT':
        # check that request content is json and accepts json response
        helpers.check_req_content_is_json(request)
        helpers.check_accepts_json_res(request)
        # verify jwt and get boat
        token = helpers.verify_jwt(request)
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        # check boat exists
        if not boat:
            abort(404, description="Boat not found")
        # check that boat belongs to the user
        helpers.check_auth(boat.get('owner'), token.get('sub'))
        content = request.get_json()
        # check that boat belongs to the user
        _verify_boat_content(content)
        boat = _update_boat_content(content, boat)
        # unload loads from boat
        _unload_loads(boat)
        boat.update({'loads': []})
        client.put(boat)
        # return replaced boat with ids and self links
        boat = _add_ids_and_self_links(boat)
        return helpers.create_response(boat, 201, constants.json)
    # Delete boat
    elif request.method == 'DELETE':
        # verify jwt and get boat
        token = helpers.verify_jwt(request)
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        # check boat exists
        if not boat:
            abort(404, description="Boat not found")
        # verify boat belongs to user
        helpers.check_auth(boat.get('owner'), token['sub'])
        # unload all loads and delete boat
        _unload_loads(boat)
        client.delete(boat_key)
        return helpers.create_response(None, 204, None)
    else:
        abort(405, description="Method Not Allowed")


@bp.route('/<boat_id>/<load_id>', methods=['PATCH', 'DELETE'])
def add_delete_load_to_boat(boat_id, load_id):
    # Add load to boat
    if request.method == 'PATCH':
        # get token
        token = helpers.verify_jwt(request)
        # get boat
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        # check boat exists
        if not boat:
            abort(404, description="Boat not found")
        # check boat auth
        helpers.check_auth(boat.get('owner'), token['sub'])
        # get load
        load_key = client.key(constants.loads, int(load_id))
        load = client.get(key=load_key)
        # check load exists and is not on a boat
        if not load:
            abort(404, description="Load not found")
        if load.get('boat'):
            abort(403, description="Load is already on a boat")
        # put load on boat
        load.update({'boat': {'id': int(boat_id)}})
        loads = boat.get('loads')
        loads.append({'id': int(load_id)})
        boat.update({'loads': loads})
        client.put(load)
        client.put(boat)
        return helpers.create_response(None, 204, None)
    elif request.method == 'DELETE':
        # get token
        token = helpers.verify_jwt(request)
        # get boat
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        if not boat:
            abort(404, description="Boat not found")
        # check boat auth
        helpers.check_auth(boat.get('owner'), token['sub'])
        # get load
        load_key = client.key(constants.loads, int(load_id))
        load = client.get(key=load_key)
        # check load exists and is on the boat
        if not load:
            abort(404, description="Load not found")
        if not _check_load_on_boat(boat, load):
            abort(404, description="Load is not on this boat")
        # remove load from boat
        load.update({'boat': None})
        loads = boat.get('loads')
        loads.remove({'id': int(load_id)})
        boat.update({'loads': loads})
        client.put(load)
        client.put(boat)
        return helpers.create_response(None, 204, None)
    else:
        abort(405, description="Method Not Allowed")


# unload all loads from boat
def _unload_loads(boat):
    if boat.get('loads'):
        for l in boat.get('loads'):
            load_key = client.key(constants.loads, l.get('id'))
            load = client.get(key=load_key)
            if load:
                if load.get('boat').get('id') == boat.id:
                    load.update({'boat': None})
                    client.put(load)


# add ids and self links to boat
def _add_ids_and_self_links(boat):
    boat.update({'id': boat.id, 'self': request.url_root + constants.boats + '/' + str(boat.id)})
    # add self links for all loads
    if boat.get('loads'):
        boat.update({'self': request.url_root + constants.loads + '/' + str(l.get('id')) for l in boat.get('loads')})
    return boat


# check if load in on the boat
def _check_load_on_boat(boat, load):
    if boat.get('loads'):
        for l in boat.get('loads'):
            if l.get('id') == load.id:
                return True
    return False


# verify all boat properties are present and valid
def _verify_boat_content(content):
    if _verify_name(content.get('name')) and \
        _verify_type(content.get('type')) and \
            _verify_length(content.get('length')):
        return True


# update all boat properties with valid content
def _update_boat_content(content, boat):
    if content.get('name'):
        _verify_name(content.get('name'))
        boat.update({'name': content.get('name')})
    if content.get('type'):
        _verify_type(content.get('type'))
        boat.update({'type': content.get('type')})
    if content.get('length'):
        _verify_length(content.get('length'))
        boat.update({'length': content.get('length')})
    return boat


# verify name property
def _verify_name(n):
    if not helpers.verify_string(n):
        abort(400, description="At least one required property is invalid or missing")
    return n


# verify type property
def _verify_type(t):
    if not helpers.verify_string(t):
        abort(400, description="At least one required property is invalid or missing")
    return t


# verify length property
def _verify_length(l):
    if not helpers.verify_pos_int(l):
        abort(400, description="At least one required property is invalid or missing")
    return l
