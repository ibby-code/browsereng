console.log("loaded comment!");

var strong = document.querySelectorAll("strong")[0];
var allowSubmit = true;

function lengthCheck(evt) {
    var value = this.value || "";
    var displayValue = "";
    var lengthModifier = evt.value === "backspace" ? -1 : 1;
    allowSubmit = value.length + lengthModifier <= 10;
    if (!allowSubmit) {
        displayValue = "Comment too long!";
    } 
    strong.innerHTML = displayValue;
}

var inputs = document.querySelectorAll("input");
for (var i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener("keydown", lengthCheck);
}

var form = document.querySelectorAll("form")[0];
if (form) {
    form.addEventListener("submit", function(e) {
        if (!allowSubmit) e.preventDefault();
    });
}