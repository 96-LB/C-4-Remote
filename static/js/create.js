function add_field(type, count=1, values=[])
{
    if(typeof this.counts === 'undefined')
    {
        this.counts = {};
    }
    const types = {
        'test': 
`           
            <legend>Test #</legend>
            <label class="flex_grow">
                <input name="visible_#" type="hidden" value="$"><input type="checkbox">Visible
            </label>
            <textarea name="input_#" placeholder="Input" wrap="off" rows=5 maxlength=1048576>$</textarea>
            <textarea name="output_#" placeholder="Output" wrap="off" rows=5 maxlength=1048576>$</textarea>
`,
        'image':
`
            <legend>Image #</legend>
            <label class="flex-grow"><input name="filename_img_#" type="text" placeholder="Filename" value="$"></label>
            <input name="img_#" type="file" accept="image/*">
`};
    const maxes = {'test': 20, 'image': 10};
    const sender = document.getElementById('create_div_' + type);
    if(!this.counts.hasOwnProperty(type))
    {
        this.counts[type] = 0;
    }
    for(var i = 0; i < count; i++)
    {
        if(this.counts[type] >= maxes[type])
        {
            break;
        }
        var field = document.createElement('fieldset');
        field.className = 'flex'
        field.id = `field_${type}_${++this.counts[type]}`;
        var inner = types[type].replace(/#/g, this.counts[type]);
        if(i < values.length)
        {
            var val = values[i];
            if(!Array.isArray(val))
            {
                val = [val];
            }
            inner = inner.split('$');
            inner = inner.slice(1).reduce((out, current, index) => out + (index < val.length ? escape(val[index]) : '') + current, inner[0])
        }
        else
        {
            inner = inner.replace(/\$/g, '');
        }
        field.innerHTML = inner;
        sender.parentNode.insertBefore(field, sender); 
    }
    for(var i = 0; i < -count; i++)
    {
        if(this.counts[type] <= 0)
        {
            break;
        }
        var del = document.getElementById(`field_${type}_${this.counts[type]--}`);
        del.parentNode.removeChild(del);
    }
    setup();
}

function setup()
{
    [...document.querySelectorAll('input[name^=filename]')].forEach(elem => {
        elem.oninput = checkFilename;
        elem.pattern = '[a-z0-9-_]+';
        elem.value = filenamify(elem.value, false);
    });
    [...document.querySelectorAll('input[type=file]')].forEach(elem => {
        elem.onchange = checkFile;
    });
    [...document.querySelectorAll('input[type=checkbox]')].forEach(elem => {
        elem.checked = elem.previousSibling.value == '1';
        elem.onclick = toggle;
    });
    document.querySelector('#create_form').onsubmit = upload;
}

function checkFilename(e)
{
    e = e || window.event;
    var sender = e.srcElement || e.target;
    var pos = sender.selectionStart;
    var substring = sender.value.substring(0, sender.selectionStart);
    sender.value = filenamify(sender.value, false);
    sender.selectionEnd = pos - substring.length + filenamify(substring, false).length;
}

function checkFile(e)
{
    e = e || window.event;
    var sender = e.srcElement || e.target;
    var target = sender.previousElementSibling.firstElementChild
    if(sender.files[0].size > 1024 * 1024 * 5)
    {
        alert('Image size cannot exceed 5MB.')
        sender.value = '';
    }
    target.value = filenamify(sender.files[0].name, true);
}

function toggle(e)
{
    e = e || window.event;
    var sender = e.srcElement || e.target;
    sender.previousSibling.value = 1 - sender.previousSibling.value;
}

function filenamify(str, extension)
{
    const remove = extension ? /\.[^.]*$|[^a-z0-9-_]/g : /[^a-z0-9-_]/g; 
    const disallowed = 'CON PRN AUX CLOCK NUL COM1 COM2 COM3 COM4 COM5 COM6 COM7 COM8 COM9 LPT1 LPT2 LPT3 LPT4 LPT5 LPT6 LPT7 LPT8 LPT9'.split(' ');
    str = str.toLowerCase().replace(/\s/g, '_').replace(remove, '');
    if(disallowed.includes(str.toUpperCase()))
    {
        str += '_';
    }
    if(str.length > 32)
    {
        str = str.substring(0, 32);
    }
    return str;
}

function upload(e)
{
    e = e || window.event;
    var sender = e.srcElement || e.target;
    if(sender.checkValidity())
    {
        e.preventDefault();
        
        var form = new FormData(sender);
        sender.querySelector('input[type=submit]').disabled = true;
        sender.querySelector('img.load_img').style.visibility = 'visible';
        fetch('/problems/' + (new URLSearchParams(window.location.search).get('edit') || form.get('filename')), {method: 'POST', body: form}).then(x => x.json()).then(x => {
            if(x['ok'])
            {
                window.location.href = '/problems';
            }
            else
            {
                sender.querySelector('img.load_img').style.visibility = 'hidden';
                alert(x['message']);
                sender.querySelector('input[type=submit]').disabled = false;
            }
        });
    }
}

function escape(string) {
    return String(string).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

window.onload = setup;