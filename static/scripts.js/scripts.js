function handleFileSelect(event) {
    console.log("Files selected:", event.target.files);
}

function submitListing(event) {
    event.preventDefault();

    const form = document.getElementById('listingForm');
    const formData = new FormData(form);

    fetch('/submit_listing', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        console.log(data);
    })
    .catch(error => {
        alert('Error submitting form');
        console.error('Error:', error);
    });
}
