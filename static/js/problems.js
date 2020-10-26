function deleteProblem(problem)
{
    return function(e)
    {
        e = e || window.event;
        var sender = e.srcElement || e.target;
        if(confirm(`Are you sure you want to delete the problem "${problem}"?`))
        {
            var del = false;
            sender.disabled = true;
            sender.parentNode.querySelector('img.load_img').style.visibility = 'visible';
            fetch('/problems/' + problem, {method: 'DELETE'}).then(x => {
                del = x.status == 200 || x.status == 404;
                return x.json();
            }).then(x => {
                if(!x['ok'])
                {
                    alert(x['message']);
                }
                if(del)
                {
                    var elem = document.getElementById('problems_field_' + problem)
                    if(elem)
                    {
                        elem.parentNode.removeChild(elem);
                    }
                }
                else
                {
                    sender.parentNode.querySelector('img.load_img').style.visibility = 'hidden';
                    sender.disabled = false;
                }
            });
        }
    };
}

function setup()
{
    [...document.querySelectorAll('button.problems_btn[name=delete]')].forEach(elem => {
        elem.onclick = deleteProblem(elem.value);
    });
}

window.onload = setup