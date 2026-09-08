frappe.ui.form.on("Moyasar Settings", {
  refresh(frm) {
    if (!frm.is_new()) {
      frm.add_custom_button(__("Test API Connection"), () => {
        frm.call("test_connection").then((response) => {
          frappe.msgprint({
            title: __("Connection Successful"),
            message: response.message,
            indicator: "green",
          });
        });
      });

      frm.add_custom_button(__("Copy Webhook URL"), () => {
        frappe.utils.copy_to_clipboard(frm.doc.webhook_url || "");
      });
    }
  },
});
