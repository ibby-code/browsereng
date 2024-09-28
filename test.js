console.log(document.querySelectorAll("a")[0].getAttribute("href"));

console.log("hello");
console.log(true);
console.log(5);
console.log([2, "bye", {"1": 2}, [9, 3]]);

var targetEl = document.querySelectorAll(".target")[0];
function handleKeyDown() {
  var value = this.getAttribute("value");
  targetEl.innerHTML = "<b>" + value + "</b";
}

var inputs = document.querySelectorAll("input");
for (var i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener("keydown", handleKeyDown);
}