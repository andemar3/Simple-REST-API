import json
from google.cloud import datastore
from flask import abort, Flask, make_response, request
from jose import jwt
from six.moves.urllib.request import urlopen
import auth_constants
import constants

app = Flask(__name__)
client = datastore.Client()


# create a response from content, status code, and content type header
def create_response(content, status, content_type):
    # create a response from content and set status code and Content-Type header
    if content:
        res = make_response(content)
    else:
        res = make_response()
    if content_type:
        res.headers.set('Content-Type', content_type)
    if status:
        res.status_code = status
    return res


# check that request body is json
def check_req_content_is_json(req):
    if not req.is_json:
        abort(415, description="Request content is not json")


# check that requester accepts json response
def check_accepts_json_res(req):
    if constants.json not in req.accept_mimetypes:
        abort(406, description="Must accept json response")


# Create a new item in the database
def create_new_item(content, item_kind):
    new_item = datastore.entity.Entity(key=client.key(item_kind))
    return update_and_put_item(content, new_item)


# Edit an item in the database
def update_and_put_item(content, item):
    item.update({key: content[key] for key in content})
    client.put(item)
    return item


# find the user id that matches the given sub
def get_user_id_from_sub(sub):
    query = client.query(kind=constants.users)
    query = query.add_filter('sub', '=', sub)
    results = list(query.fetch())
    return results[0].id


# Get list of items
def fetch_list(item_kind):
    query = client.query(kind=item_kind)
    return list(query.fetch())


# Get filtered and paginated list of items
def fetch_filtered_and_paginated_list(item_kind, limit=constants.MAX_LIMIT, offset=0, filter=()):
    query = client.query(kind=item_kind)
    if filter:
        query = query.add_filter(filter[0], filter[1], filter[2])
    iterator = query.fetch(limit=limit, offset=offset)
    results = list(next(iterator.pages))
    print(results)
    output = {item_kind: results}
    # get next link and total items count
    if iterator.next_page_token:
        next_url = request.base_url + "?limit=" + str(limit) + "&offset=" + str(offset + limit)
        output['next'] = next_url
    query = client.query(kind=item_kind)
    if filter:
        query = query.add_filter(filter[0], filter[1], filter[2])
    output['total'] = len(list(query.fetch()))
    return output


# add an owner to an item
def add_owner(item, sub):
    item.update({'owner': get_user_id_from_sub(sub)})
    return item


# check if string is valid
def verify_string(s):
    if s and \
            type(s) is str \
            and s != '' \
            and len(s) <= constants.MAX_STR_LEN:
        return True
    return False


# check if integer is valid
def verify_pos_int(n):
    if n and \
            type(n) is int \
            and n > 0:
        return True
    return False


# check if the user at usr_id matches sub
def check_auth(usr_id, sub):
    usr_key = client.key(constants.users, usr_id)
    usr = client.get(key=usr_key)
    if sub != usr.get('sub'):
        abort(403, description="You are not authorized to access this resource")


# check if jwt is valid
def verify_jwt(request):
    # check for Authorization header
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization'].split()
        token = auth_header[1]
    else:
        abort(401, description="Authorization header is missing")
    # get known jwts
    jsonurl = urlopen("https://" + auth_constants.AUTH0_DOMAIN + "/.well-known/jwks.json")
    jwks = json.loads(jsonurl.read())
    # decode headers
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.JWTError:
        abort(401, description="Invalid header: Use an RS256 signed JWT Access Token")
    if unverified_header["alg"] == "HS256":
        abort(401, description="Invalid header: Use an RS256 signed JWT Access Token")
    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    # decode jwt if rsa key found
    if rsa_key:
        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=auth_constants.AUTH0_CLIENT_ID,
                issuer="https://" + auth_constants.AUTH0_DOMAIN + "/"
            )
        except jwt.ExpiredSignatureError:
            abort(401, description="Token is expired")
        except jwt.JWTClaimsError:
            abort(401, description="Invalid claims: Please check the audience and issuer")
        except Exception:
            abort(401, description="Invalid header: Unable to parse authentication")
        return payload
    else:
        abort(401, description="No RSA key in JWKS")
