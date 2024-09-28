console.log(document.querySelectorAll("a")[0].getAttribute("href"));

console.log("hello");
console.log(true);
console.log(5);
console.log([2, "bye", {"1": 2}, [9, 3]]);

function handleKeyDown() {
  var name = this.getAttribute("name");
  var value = this.getAttribute("value");
  console.log(name, value);
}

var inputs = document.querySelectorAll("input");
for (var i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener("keydown", handleKeyDown);
}