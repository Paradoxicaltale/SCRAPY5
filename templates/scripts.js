document.getElementById('listingForm').addEventListener('submit', function(event) {
    event.preventDefault();

    const form = document.getElementById('listingForm');
    const formData = new FormData(form);

    fetch('/submit_listing', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        const messageContainer = document.getElementById('responseMessage');
        if (data.success) {
            messageContainer.innerHTML = `<div class="success-message">${data.message}</div>`;
            form.reset();
        } else {
            messageContainer.innerHTML = `<div class="error-message">${data.message}</div>`;
        }
    })
    .catch(error => {
        document.getElementById('responseMessage').innerHTML =
            `<div class="error-message">An error occurred: ${error.message}</div>`;
    });
});
