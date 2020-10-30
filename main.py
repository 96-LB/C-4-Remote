import gzip, json, base64, flask, threading, os, time, functools
from io import BytesIO
import pydrive.auth, pydrive.drive, pydrive.files
import bcrypt
import flask_limiter, flask_limiter.util

drive = None
gauth = None

app = flask.Flask('')
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 5
app.config['SECRET_KEY'] = base64.b64decode(os.getenv('KEY'))
app.config['AUTH_TIMEOUT'] = 60 * 60 # one hour

limiter = flask_limiter.Limiter(app, key_func=flask_limiter.util.get_remote_address)
rate_limit = limiter.shared_limit("1/second;30/minute", scope="gdrive")

@app.before_request
def run_auth():
    is_auth(True)

def is_auth(refresh=False):
    if refresh or not flask.g.auth:
        login = False
        timeout = False
        if 'auth' not in flask.session:
            flask.session['auth'] = None
        if flask.session['auth'] is not None:
            timeout = time.time() - flask.session['auth'] > app.config['AUTH_TIMEOUT']
            if timeout: print(flask.request.endpoint)
            login = not timeout
        flask.session['auth'] = time.time() if login else None
        flask.g.auth = {'ok': login, 'message': 'Sucessfully authorized.' if login else 'Your session has expired. Refresh the page to log in again.' if timeout else 'You must log in to perform this action.'}
    return flask.g.auth

app.jinja_env.globals.update(is_auth=is_auth)

def needs_auth(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        authed = is_auth()
        if not authed['ok']:
            if flask.request.method == "GET":
                return flask.redirect(flask.url_for('route_login', next=flask.request.full_path))
            else:
                return authed, 403
        return f(*args, **kwargs)
    return wrapper

def needs_gauth(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        global gauth, drive
        if gauth is None or gauth.access_token_expired:
            gauth = pydrive.auth.GoogleAuth()
            gauth.credentials = pydrive.auth.ServiceAccountCredentials.from_json_keyfile_dict(json.loads(base64.b64decode(os.getenv('AUTH'))), ['https://www.googleapis.com/auth/drive'])
            drive = pydrive.drive.GoogleDrive(gauth)
        return f(*args, **kwargs)
    return wrapper

needs_gauth(lambda: None)()

for i in os.listdir('Problems/'):
    os.remove('Problems/' + i)
for i in drive.ListFile().GetList():
    i.GetContentFile('Problems/' + i['title'])


@app.errorhandler(429)
@app.errorhandler(pydrive.files.ApiRequestError)
def rate_limited(e):
    return {'ok': False, 'message': 'You are performing this action too quickly. You must wait before trying again.'}, 429

@app.route('/favicon.ico')
def route_favicon():
    return flask.send_from_directory('static', filename='img/favicon.ico')



@app.route('/')
def route_index():
    return flask.render_template('index.html')



@app.route('/problems', methods=['GET', 'POST'])
def route_problems():
    return {'GET': route_problems_get, 'POST': route_problems_post}[flask.request.method]()
    
@needs_auth
def route_problems_get():
    return flask.render_template('problems.html', problems=os.listdir('Problems'))
    
def route_problems_post():
    out = {}
    for filename in os.listdir('Problems'):
        with open('Problems/' + filename, 'rb') as f:
            f.seek(-12, os.SEEK_END)
            out[filename] = base64.b64encode(f.read()).decode('utf8')
    return json.dumps(out)



@app.route('/create')
@needs_auth
def route_create():
    filename = flask.request.args.get('edit')
    problem = None if filename is None else unproblem(filename)
    if problem is not None:
        problem['tests'] = [[int(i['visible']), i['input'], i['output']] for i in problem['tests']]
        problem['images'] = list(problem['images'].keys())
    return flask.render_template('create.html', filename=os.path.splitext(filename or '')[0], problem=problem)



@app.route('/problems/<name>', methods=['GET', 'POST', 'DELETE'])
def route_problem(name):
    return {'GET': route_problem_get, 'POST': route_problem_post, 'DELETE': route_problem_delete}[flask.request.method](name)

def route_problem_get(name):
    return flask.send_file('Problems/' + name, as_attachment=True)

@needs_auth
@needs_gauth
@rate_limit
def route_problem_post(oldname):
    old = unproblem(oldname)

    name = flask.request.form.get('name')
    filename = flask.request.form.get('filename')
    text = flask.request.form.get('text')

    if any(i is None or len(i.strip()) == 0 for i in [name, filename, text]):
        return {'ok': False, 'message': f'missing name/filename/text\n{name}\n{filename}\n{text}'}

    tests = []
    for i in range(1, 26):
        test = {'visible': flask.request.form.get('visible_' + str(i)) == '1', 'input': flask.request.form.get('input_' + str(i)), 'output': flask.request.form.get('output_' + str(i))}
        if all(test[i] is not None and len(str(test[i]).strip()) > 0 for i in test):
            tests.append(test)

    
    images = {}
    for i in range(1, 11):
        imgname = flask.request.form.get('filename_img_' + str(i))
        img = flask.request.files.get('img_' + str(i))
        if imgname is not None and img is not None:
            img = img.read()
            imgname = filenamify(imgname, False)
            if len(img) == 0:
                if old and imgname in old['images']:
                    oldimg = old['images'][imgname]
                    if oldimg:
                     images[imgname] = oldimg
            else:
                images[imgname] = b64(img)
    
    problem(filenamify(filename, True), oldname=oldname, name=namify(name), text=text[:1024*1024], tests=tests, images=images)
    return {'ok': True, 'message': 'made problem'}

@needs_auth
@needs_gauth
@rate_limit
def route_problem_delete(name):
    gfiles = drive.ListFile({'q': f" title='{name}' "}).GetList()
    if not gfiles:
        return {'ok': False, 'message': f'No problem "{name}" exists.'}, 404
    gfiles[0].Delete()
    if os.path.exists('Problems/' + name):
        os.remove('Problems/' + name)
    return {'ok': True, 'message': f'Successfully deleted problem "{name}".'}



@app.route('/login', methods=['GET', 'POST'])
def route_login():
    if flask.request.method == 'GET':
        return flask.redirect(flask.request.args.get('next') or flask.url_for('route_index')) if is_auth()['ok'] else flask.render_template('login.html')
    elif flask.request.method == 'POST':
        flask.session['auth'] = None
        json = flask.request.json
        password = json.get('password') if json else None
        out = {'ok': False, 'message': 'You must supply a password.'}
        if password:
            out['ok'] = bcrypt.checkpw(str(password).encode('utf-8'), os.getenv('PW').encode('utf-8'))
            if out['ok']:
                flask.session['auth'] = time.time()
                out['message'] = 'Successfully logged in.'
            else:
                out['message'] = 'Incorrect password.'
        return out
    


@app.route('/logout')
def route_logout():
    flask.session['auth'] = None
    run_auth()
    return flask.render_template('logout.html')



def run():
    app.run(host='0.0.0.0', port=8080)
threading.Thread(target=run).start()






def compress(bytes):
    if type(bytes) is str:
        bytes = bytearray(bytes, encoding='utf8')
    return gzip.compress(bytes)

def decompress(bytes):
    return gzip.decompress(bytes).decode("utf8")

def checksum(string):
    #print('---')
    #print(list(string))
    #print('---')
    mask = (1 << 96) - 1
    out = mask
    with BytesIO(string) as f:
        while True:
            nbytes = f.read(12)
            if len(nbytes) == 0:
                break
            out ^= int.from_bytes(nbytes, 'little')
            out <<= 1
            out |= out >> 96
            out &= mask
    #print(list(out.to_bytes(12, byteorder='big')[::-1]))
    return out.to_bytes(12, byteorder='big')[::-1]

def problem(filename, oldname=None, **kwargs):
    out = {}
    for k, v in kwargs.items():
        out[k] = v
    #print(json.dumps(out))
    #print(compress(json.dumps(out)))
    #print(checksum(compress(json.dumps(out))))
    #print(json.dumps(out))
    #print(len(json.dumps(out)))
    compressed = compress(json.dumps(out))
    #print(len(compressed))
    with open('Problems/' + filename, 'wb') as file:
        #print('-----' + str(list(compressed)))
        file.write(compressed)
        check = checksum(compressed)
        #print(check)
        file.write(check)
    if oldname and oldname != filename and os.path.exists('Problems/' + oldname):
        os.remove('Problems/' + oldname)
    gfiles = drive.ListFile({'q': f" title='{oldname or filename}' "}).GetList()
    file = drive.CreateFile({'id': gfiles[0]['id']} if gfiles else {'title': filename}) 
    file['title'] = filename
    file.Upload()
    file.SetContentFile('Problems/' + filename)
    file.Upload()

def unproblem(filename):
    try:
        with open('Problems/' + filename, 'rb') as file:
            file.seek(-12, os.SEEK_END)
            length = file.tell()
            check = file.read()
            file.seek(0)
            data = file.read(length)
            if check != checksum(data):
                print(f'CHECKSUM: {check} - {checksum(data)}')
                return None
            decompressed = json.loads(decompress(data))
            return decompressed
    except Exception as e:
        print('ERROR (unproblem): ' + str(e))
        return None

def b64(str):
    return base64.b64encode(str).decode('utf8')

def namify(name):
    return ' '.join(name.split())[:32]

def filenamify(name, extension):
    allowed = 'abcdefghijklmnopqrstuvwyxzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
    disallowed = 'CON PRN AUX CLOCK NUL COM1 COM2 COM3 COM4 COM5 COM6 COM7 COM8 COM9 LPT1 LPT2 LPT3 LPT4 LPT5 LPT6 LPT7 LPT8 LPT9'.split(' ')
    name = ''.join(i.lower() for i in name if i in allowed)[:32]
    if not name or name.upper() in disallowed:
        name += '_'
    if extension:
        name += '.c4'
    return name