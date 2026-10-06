import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TOL = 0.05


class LineItem(BaseModel):
    name: str = Field(description="item name as printed, cleaned up")
    quantity: float = Field(1, gt=0, description="number of units")
    total: float = Field(description="line total for all units")


class Receipt(BaseModel):
    merchant: str = Field(description="shop or business name, no branch number or address")
    date: dt.date = Field(description="purchase date, YYYY-MM-DD")
    currency: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217 code, e.g. USD, EUR, INR; infer from symbols or location")
    items: list[LineItem]
    subtotal: float | None = Field(None, description="sum of the line item totals")
    discount: float | None = Field(None, ge=0, description="total discount as a positive number, null if none")
    tax: float | None = Field(None, ge=0, description="total tax, summing all tax lines; null if not shown")
    tax_included: bool = Field(False, description="true if tax is already inside the item prices (VAT/MwSt style)")
    tip: float | None = Field(None, ge=0)
    total: float = Field(description="final amount paid")
    payment_method: Literal["cash", "card", "mobile", "other"] | None = Field(
        None, description="mobile = phone wallets and UPI (Apple Pay, Google Pay, UPI)")

    @model_validator(mode="after")
    def amounts_add_up(self):
        if self.items and self.subtotal is not None:
            s = round(sum(i.total for i in self.items), 2)
            if abs(s - self.subtotal) > TOL:
                raise ValueError(f"line items sum to {s} but subtotal is {self.subtotal}")
        if self.subtotal is not None:
            expect = self.subtotal - (self.discount or 0) + (self.tip or 0)
            if not self.tax_included:
                expect += self.tax or 0
            if abs(expect - self.total) > TOL:
                raise ValueError(
                    f"subtotal - discount + tax + tip = {round(expect, 2)} but total is {self.total} "
                    "(check tax_included, discount sign, and missed lines)")
        return self


class JobPost(BaseModel):
    title: str = Field(description="job title without team or location")
    company: str = Field(description="hiring company, or the recruiter if the client is unnamed")
    location: str | None = Field(None, description="office city (and region/country if given); null for fully remote roles")
    work_mode: Literal["onsite", "hybrid", "remote"]
    employment_type: Literal["full-time", "part-time", "contract", "internship"]
    salary_min: float | None = Field(None, description="plain number in full units, e.g. 8 LPA -> 800000")
    salary_max: float | None = Field(None, description="same as salary_min when a single figure is given")
    salary_currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    salary_period: Literal["hour", "day", "month", "year"] | None = None
    min_years_experience: int | None = Field(None, ge=0, description="0 if the post says no experience needed")
    skills: list[str] = Field(default_factory=list, description="required technologies and skills, one per entry, not nice-to-haves")
    apply_by: dt.date | None = Field(None, description="application deadline, YYYY-MM-DD")

    @model_validator(mode="after")
    def salary_consistent(self):
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError(f"salary_min {self.salary_min} is larger than salary_max {self.salary_max}")
        if (self.salary_min is not None or self.salary_max is not None) and not (self.salary_currency and self.salary_period):
            raise ValueError("salary given but salary_currency or salary_period is missing")
        return self


SCHEMAS = {"receipt": Receipt, "job_post": JobPost}
