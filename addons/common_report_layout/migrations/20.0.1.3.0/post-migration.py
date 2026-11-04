def migrate(cr, version):
    """Document Details lines: Field Type + Field + Key Field become one field
    path, e.g. user_id + name -> 'user_id.name'."""
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'report_document_line' AND column_name = 'field_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE report_document_line line
           SET field_path = (
                   SELECT name FROM ir_model_fields WHERE id = line.field_id
               ) || COALESCE(
                   CASE WHEN line.ttype IN ('many2one', 'one2many', 'many2many')
                        THEN '.' || (
                            SELECT name FROM ir_model_fields
                            WHERE id = line.field_key_id
                        )
                   END,
                   ''
               )
         WHERE line.field_path IS NULL
           AND line.field_id IS NOT NULL
        """
    )
