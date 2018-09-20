# -*- coding: utf-8 -*-
# © 2016 Yannick Vaucher (Camptocamp)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from openerp import api, models
from openerp.exceptions import UserError


class AccountBankStatementLine(models.Model):

    _inherit = 'account.bank.statement.line'

    @api.multi
    def get_reconciliation_proposition(self, excluded_ids=None):
        """ Look for transaction_ref to give them as proposition move line """
        if self.name:
            # If the transaction has no partner, look for match in payable and
            # receivable account anyway
            overlook_partner = not self.partner_id
            domain = [('transaction_ref', 'ilike', self.name)]
            match_recs = self.get_move_lines_for_reconciliation(
                excluded_ids=excluded_ids, limit=2, additional_domain=domain,
                overlook_partner=overlook_partner)
            if match_recs and len(match_recs) == 1:
                return match_recs
        _super = super(AccountBankStatementLine, self)
        return _super.get_reconciliation_proposition(excluded_ids=excluded_ids)

    @api.multi
    def auto_reconcile(self):
        """ Look for transaction_ref to identify potential move line for auto reconcile. """
        if self.name:
            overlook_partner = not self.partner_id
            domain = [('transaction_ref', 'ilike', self.name)]
            match_recs = self.get_move_lines_for_reconciliation(limit=2, additional_domain=domain,
                overlook_partner=overlook_partner)
            if match_recs and len(match_recs) == 1:
                # Now reconcile
                counterpart_aml_dicts = []
                payment_aml_rec = self.env['account.move.line']
                for aml in match_recs:
                    if aml.account_id.internal_type == 'liquidity':
                        payment_aml_rec = (payment_aml_rec | aml)
                    else:
                        amount = aml.currency_id and aml.amount_residual_currency or aml.amount_residual
                        counterpart_aml_dicts.append({
                            'name': aml.name if aml.name != '/' else aml.move_id.name,
                            'debit': amount < 0 and -amount or 0,
                            'credit': amount > 0 and amount or 0,
                            'move_line': aml
                        })

                try:
                    with self._cr.savepoint():
                        counterpart = self.process_reconciliation(counterpart_aml_dicts=counterpart_aml_dicts,
                                                                  payment_aml_rec=payment_aml_rec)
                    return counterpart
                except UserError:
                    # A configuration / business logic error that makes it impossible to auto-reconcile should not be raised
                    # since automatic reconciliation is just an amenity and the user will get the same exception when manually
                    # reconciling. Other types of exception are (hopefully) programmation errors and should cause a stacktrace.
                    self.invalidate_cache()
                    self.env['account.move'].invalidate_cache()
                    self.env['account.move.line'].invalidate_cache()
                    return False

        _super = super(AccountBankStatementLine, self)
        return _super.auto_reconcile()
