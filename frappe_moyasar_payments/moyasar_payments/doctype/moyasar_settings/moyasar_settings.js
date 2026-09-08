frappe.ui.form.on("Moyasar Settings", {
  refresh(frm) {
    if (!frm.is_new()) {
      frm.add_custom_button(__("Copy Webhook URL"), () => {
        frappe.utils.copy_to_clipboard(frm.doc.webhook_url || "");
      });
    }
  },
});
