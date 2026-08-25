"""Reusable database access primitives.

CRUD objects only read or mutate the current SQLAlchemy session. Transaction
boundaries belong to the service layer so multiple CRUD operations can be
committed atomically.
"""
