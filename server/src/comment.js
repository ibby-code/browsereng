console.log("loaded comment!");

var strong = document.querySelectorAll("strong")[0];

function lengthCheck() {
    var value = this.getAttribute("value") || "";
    var displayValue = "";
    if (value.length > 10) {
        displayValue = "Comment too long!";
    } 
    strong.innerHTML = displayValue;
}

var inputs = document.querySelectorAll("input");
for (var i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener("keydown", lengthCheck);
}