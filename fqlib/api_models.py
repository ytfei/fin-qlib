# Copyright (c) 2024
# Licensed under the MIT License.

"""
API request and response models for the backtest service.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class PredictionRequest(BaseModel):
    """Request model for stock prediction."""

    date: str = Field(
        ...,
        description="Target date for prediction (format: YYYY-MM-DD)",
        json_schema_extra={"example": "2025-01-10"}
    )

    @field_validator('date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Validate date format and value."""
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('date must be in YYYY-MM-DD format')
        return v


class StockPrediction(BaseModel):
    """Prediction result for a single stock."""

    instrument: str = Field(..., description="Stock code/ticker")
    score: float = Field(..., description="Prediction score")
    rank: Optional[int] = Field(None, description="Rank among all stocks")


class PredictionResponse(BaseModel):
    """Response model for stock prediction."""

    date: str = Field(..., description="Prediction date")
    predictions: List[StockPrediction] = Field(
        ...,
        description="List of stock predictions"
    )
    total_count: int = Field(..., description="Total number of predictions")
    top_n: Optional[List[StockPrediction]] = Field(
        None,
        description="Top N predictions (default: top 10)"
    )


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Detailed error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    manager_loaded: bool = Field(..., description="Whether manager is loaded")
    current_time: Optional[str] = Field(None, description="Current manager time")
    strategies: List[str] = Field(..., description="Available strategies")


class BatchPredictionRequest(BaseModel):
    """Request model for batch prediction."""

    start_date: str = Field(
        ...,
        description="Start date for prediction (format: YYYY-MM-DD)",
        json_schema_extra={"example": "2025-01-01"}
    )
    end_date: str = Field(
        ...,
        description="End date for prediction (format: YYYY-MM-DD)",
        json_schema_extra={"example": "2025-01-10"}
    )

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Validate date format and value."""
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('date must be in YYYY-MM-DD format')
        return v


class DatePrediction(BaseModel):
    """Prediction result for a single date."""

    date: str = Field(..., description="Prediction date")
    predictions: List[StockPrediction] = Field(
        ...,
        description="List of stock predictions"
    )
    total_count: int = Field(..., description="Total number of predictions")


class BatchPredictionResponse(BaseModel):
    """Response model for batch prediction."""

    predictions: List[DatePrediction] = Field(
        ...,
        description="List of predictions for each date"
    )
    total_dates: int = Field(..., description="Total number of dates processed")
