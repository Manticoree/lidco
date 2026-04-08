"""Tests for lidco.envmgmt.promoter — EnvPromoter."""

from __future__ import annotations

import unittest

from lidco.envmgmt.promoter import (
    EnvPromoter,
    PromotionError,
    PromotionRecord,
    PromotionStatus,
)
from lidco.envmgmt.provisioner import EnvProvisioner, EnvStatus, EnvTemplate, EnvTier


def _provision(name: str, tier: EnvTier, config: dict | None = None):
    p = EnvProvisioner()
    tmpl = EnvTemplate(name=name, tier=tier, config=config or {})
    p.register_template(tmpl)
    return p.provision(name)


class TestEnvPromoter(unittest.TestCase):
    def setUp(self) -> None:
        self.promoter = EnvPromoter()
        self.dev = _provision("dev-app", EnvTier.DEV, {"port": 8080})
        self.staging = _provision("stg-app", EnvTier.STAGING, {"port": 80})
        self.prod = _provision("prd-app", EnvTier.PROD, {"port": 80})

    # -- create_promotion -----------------------------------------------------

    def test_create_promotion_dev_to_staging(self) -> None:
        rec = self.promoter.create_promotion(self.dev, self.staging)
        self.assertIsInstance(rec, PromotionRecord)
        self.assertEqual(rec.status, PromotionStatus.PENDING)

    def test_create_promotion_staging_to_prod(self) -> None:
        rec = self.promoter.create_promotion(self.staging, self.prod)
        self.assertEqual(rec.status, PromotionStatus.PENDING)

    def test_create_promotion_invalid_path(self) -> None:
        with self.assertRaises(PromotionError):
            self.promoter.create_promotion(self.dev, self.prod)

    def test_create_promotion_prod_to_dev_invalid(self) -> None:
        with self.assertRaises(PromotionError):
            self.promoter.create_promotion(self.prod, self.dev)

    def test_create_promotion_inactive_source(self) -> None:
        self.dev.status = EnvStatus.DESTROYED
        with self.assertRaises(PromotionError):
            self.promoter.create_promotion(self.dev, self.staging)

    def test_create_promotion_inactive_target(self) -> None:
        self.staging.status = EnvStatus.FAILED
        with self.assertRaises(PromotionError):
            self.promoter.create_promotion(self.dev, self.staging)

    def test_create_promotion_with_changes(self) -> None:
        rec = self.promoter.create_promotion(
            self.dev, self.staging, changes={"port": 9090}
        )
        self.assertEqual(rec.changes["port"], 9090)

    def test_create_promotion_no_approval_required(self) -> None:
        self.promoter.set_require_approval(False)
        rec = self.promoter.create_promotion(self.dev, self.staging)
        self.assertEqual(rec.status, PromotionStatus.APPROVED)

    # -- approve / reject -----------------------------------------------------

    def test_approve(self) -> None:
        rec = self.promoter.create_promotion(self.dev, self.staging)
        result = self.promoter.approve(rec.promotion_id, "admin")
        self.assertEqual(result.status, PromotionStatus.APPROVED)
        self.assertEqual(result.approved_by, "admin")

    def test_approve_not_pending(self) -> None:
        rec = self.promoter.create_promotion(self.dev, self.staging)
        self.promoter.approve(rec.promotion_id, "admin")
        with self.assertRaises(PromotionError):
            self.promoter.approve(rec.promotion_id, "admin2")

    def test_reject(self) -> None:
        rec = self.promoter.create_promotion(self.dev, self.staging)
        result = self.promoter.reject(rec.promotion_id, "bad config")
        self.assertEqual(result.status, PromotionStatus.REJECTED)
        self.assertEqual(result.error, "bad config")

    def test_reject_default_reason(self) -> None:
        rec = self.promoter.create_promotion(self.dev, self.staging)
        result = self.promoter.reject(rec.promotion_id)
        self.assertEqual(result.error, "Rejected")

    def test_reject_not_pending(self) -> None:
        rec = self.promoter.create_promotion(self.dev, self.staging)
        self.promoter.reject(rec.promotion_id)
        with self.assertRaises(PromotionError):
            self.promoter.reject(rec.promotion_id)

    # -- execute --------------------------------------------------------------

    def test_execute_success(self) -> None:
        rec = self.promoter.create_promotion(
            self.dev, self.staging, changes={"port": 9090}
        )
        self.promoter.approve(rec.promotion_id, "admin")
        result = self.promoter.execute(rec.promotion_id, self.staging)
        self.assertEqual(result.status, PromotionStatus.COMPLETED)
        self.assertEqual(self.staging.config["port"], 9090)

    def test_execute_not_approved(self) -> None:
        rec = self.promoter.create_promotion(self.dev, self.staging)
        with self.assertRaises(PromotionError):
            self.promoter.execute(rec.promotion_id, self.staging)

    def test_execute_smoke_test_pass(self) -> None:
        self.promoter.register_smoke_test(lambda env: True)
        rec = self.promoter.create_promotion(
            self.dev, self.staging, changes={"port": 9090}
        )
        self.promoter.approve(rec.promotion_id, "admin")
        result = self.promoter.execute(rec.promotion_id, self.staging)
        self.assertEqual(result.status, PromotionStatus.COMPLETED)

    def test_execute_smoke_test_fail(self) -> None:
        self.promoter.register_smoke_test(lambda env: False)
        old_config = dict(self.staging.config)
        rec = self.promoter.create_promotion(
            self.dev, self.staging, changes={"port": 9090}
        )
        self.promoter.approve(rec.promotion_id, "admin")
        result = self.promoter.execute(rec.promotion_id, self.staging)
        self.assertEqual(result.status, PromotionStatus.FAILED)
        self.assertIn("Smoke test failed", result.error)
        # Config should be rolled back
        self.assertEqual(self.staging.config["port"], old_config["port"])

    def test_execute_smoke_test_exception(self) -> None:
        def bad_test(env):
            raise RuntimeError("boom")

        self.promoter.register_smoke_test(bad_test)
        rec = self.promoter.create_promotion(
            self.dev, self.staging, changes={"port": 1111}
        )
        self.promoter.approve(rec.promotion_id, "admin")
        result = self.promoter.execute(rec.promotion_id, self.staging)
        self.assertEqual(result.status, PromotionStatus.FAILED)
        self.assertIn("boom", result.error)

    # -- rollback -------------------------------------------------------------

    def test_rollback(self) -> None:
        old_port = self.staging.config.get("port")
        rec = self.promoter.create_promotion(
            self.dev, self.staging, changes={"port": 5555}
        )
        self.promoter.approve(rec.promotion_id, "admin")
        self.promoter.execute(rec.promotion_id, self.staging)
        self.assertEqual(self.staging.config["port"], 5555)
        result = self.promoter.rollback(rec.promotion_id, self.staging)
        self.assertEqual(result.status, PromotionStatus.ROLLED_BACK)
        self.assertEqual(self.staging.config["port"], old_port)

    def test_rollback_not_completed(self) -> None:
        rec = self.promoter.create_promotion(self.dev, self.staging)
        with self.assertRaises(PromotionError):
            self.promoter.rollback(rec.promotion_id, self.staging)

    # -- query ----------------------------------------------------------------

    def test_get_record(self) -> None:
        rec = self.promoter.create_promotion(self.dev, self.staging)
        found = self.promoter.get_record(rec.promotion_id)
        self.assertIs(found, rec)

    def test_get_record_missing(self) -> None:
        self.assertIsNone(self.promoter.get_record("nope"))

    def test_list_records(self) -> None:
        self.promoter.create_promotion(self.dev, self.staging)
        self.promoter.create_promotion(self.staging, self.prod)
        self.assertEqual(len(self.promoter.list_records()), 2)

    def test_list_records_by_status(self) -> None:
        rec = self.promoter.create_promotion(self.dev, self.staging)
        self.promoter.approve(rec.promotion_id, "admin")
        pending = self.promoter.list_records(status=PromotionStatus.PENDING)
        approved = self.promoter.list_records(status=PromotionStatus.APPROVED)
        self.assertEqual(len(pending), 0)
        self.assertEqual(len(approved), 1)

    def test_promotion_not_found(self) -> None:
        with self.assertRaises(PromotionError):
            self.promoter.approve("bogus", "admin")


class TestPromotionStatus(unittest.TestCase):
    def test_status_values(self) -> None:
        self.assertEqual(PromotionStatus.PENDING.value, "pending")
        self.assertEqual(PromotionStatus.COMPLETED.value, "completed")
        self.assertEqual(PromotionStatus.ROLLED_BACK.value, "rolled_back")


if __name__ == "__main__":
    unittest.main()
