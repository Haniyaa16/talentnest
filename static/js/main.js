// Toggle the "Enter your category" textbox when "Other" is selected
document.addEventListener("DOMContentLoaded", function () {
  const categorySelect = document.getElementById("category");
  const otherWrapper = document.getElementById("otherCategoryWrapper");
  const otherInput = document.getElementById("other_category");

  if (categorySelect && otherWrapper) {
    function toggleOther() {
      if (categorySelect.value === "other") {
        otherWrapper.classList.remove("d-none");
        if (otherInput) otherInput.setAttribute("required", "required");
      } else {
        otherWrapper.classList.add("d-none");
        if (otherInput) otherInput.removeAttribute("required");
      }
    }
    categorySelect.addEventListener("change", toggleOther);
    toggleOther();
  }

  

  // Simple star rating widget for reviews
  const starContainer = document.getElementById("starRating");
  if (starContainer) {
    const stars = starContainer.querySelectorAll("i");
    const ratingInput = document.getElementById("ratingInput");
    stars.forEach((star, idx) => {
      star.addEventListener("click", () => {
        ratingInput.value = idx + 1;
        stars.forEach((s, i) => {
          s.classList.toggle("bi-star-fill", i <= idx);
          s.classList.toggle("bi-star", i > idx);
        });
      });
    });
  }
});
function togglePasswordVisibility(inputId, iconId) {
  const input = document.getElementById(inputId);
  const icon = document.getElementById(iconId);
  if (input.type === "password") {
    input.type = "text";
    icon.classList.remove("bi-eye");
    icon.classList.add("bi-eye-slash");
  } else {
    input.type = "password";
    icon.classList.remove("bi-eye-slash");
    icon.classList.add("bi-eye");
  }
}