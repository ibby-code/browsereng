console.log(document.querySelectorAll("a")[0].getAttribute("href"));

console.log("hello");
console.log(true);
console.log(5);
console.log([2, "bye", {"1": 2}, [9, 3]]);

var targetEl = document.querySelectorAll(".target")[0];
function handleKeyDown(evt) {
  var value = this.value;
  if (evt.value == "backspace") {
    value = value.slice(0, -1);
  } else {
    value += evt.value;
  }
  targetEl.innerHTML = "<b>" + value + "</b";
}

var inputs = document.querySelectorAll("input");
for (var i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener("keydown", handleKeyDown);
}