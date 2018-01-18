autosize($('textarea'));

$.validator.setDefaults({ ignore: ":hidden:not(select)" });

$('#thread-form').validate({
    errorPlacement: function (error, element) {
        if (element.is("select.custom-select")) {
            // placement for chosen
            $("div.select-section").append(error);
        } else {
            // standard placement
            error.insertAfter(element);
        }
    },
    
});


