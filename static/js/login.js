function login(e)
{
    e = e || window.event;
    var sender = e.srcElement || e.target;
    e.preventDefault();
    sender.querySelector('input[type=submit]').disabled = true;
    sender.querySelector('img.load_img').style.visibility = 'visible';
    fetch('/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({'password': document.getElementById('password').value})}).then(x => x.json()).then(x => {
        if(x['ok'])
        {
            window.location.href = new URLSearchParams(window.location.search).get('next') || '/';
        }
        else
        {
            sender.querySelector('img.load_img').style.visibility = 'hidden';
            alert(x['message']);
            sender.querySelector('input[type=submit]').disabled = false;
        }
    });
}

function setup()
{
    document.querySelector('#login_form').onsubmit = login;
}

window.onload = setup;