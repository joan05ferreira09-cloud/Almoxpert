function expandImage(img) {
    const modal = document.getElementById("imageModal");
    const expanded = document.getElementById("expandedImage");

    if (!modal || !expanded) {
        return;
    }

    expanded.src = img.src;
    modal.style.display = "flex";
}

function closeExpandedImage() {
    const modal = document.getElementById("imageModal");
    const expanded = document.getElementById("expandedImage");

    if (!modal || !expanded) {
        return;
    }

    modal.style.display = "none";
    expanded.src = "";
}

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
        closeExpandedImage();
    }
});
