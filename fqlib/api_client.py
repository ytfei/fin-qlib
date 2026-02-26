# Copyright (c) 2024
# Licensed under the MIT License.

"""
Stock Prediction API Client SDK

A simple, easy-to-use Python client for the Stock Prediction Backtest API.

Features:
- Query predictions for specific dates
- Batch query predictions for date ranges
- Health checks and status monitoring
- Built-in error handling and retry logic
- Type hints for better IDE support

Usage:
    >>> from fqlib.api_client import StockPredictionClient
    >>>
    >>> # Initialize client
    >>> client = StockPredictionClient("http://localhost:8000")
    >>>
    >>> # Check health
    >>> if client.is_healthy():
    >>>     # Get predictions for a specific date
    >>>     result = client.get_predictions("2025-01-15", top_n=10)
    >>>     print(f"Found {result['total_count']} predictions")
    >>>
    >>>     # Get available dates
    >>>     dates = client.get_available_dates()
    >>>     print(f"Available dates: {dates[0]} to {dates[-1]}")
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class StockPredictionClient:
    """
    Stock Prediction API Client

    A simple client for querying stock predictions from the backtest API.

    Attributes:
        base_url: Base URL of the API server
        timeout: Request timeout in seconds
        session: Requests session with retry logic

    Example:
        >>> client = StockPredictionClient("http://localhost:8000")
        >>> predictions = client.get_predictions("2025-01-15")
        >>> for pred in predictions['predictions']:
        ...     print(f"{pred['instrument']}: {pred['score']}")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: int = 30,
        retry_count: int = 3
    ):
        """
        Initialize the API client.

        Args:
            base_url: Base URL of the API server (default: http://localhost:8000)
            timeout: Request timeout in seconds (default: 30)
            retry_count: Number of retries for failed requests (default: 3)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

        # Create session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=retry_count,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an API request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            **kwargs: Additional arguments passed to requests

        Returns:
            JSON response as dict

        Raises:
            ConnectionError: If connection fails
            HTTPError: If HTTP status indicates error
            ValueError: If response is not valid JSON
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise ConnectionError(f"Failed to connect to {self.base_url}: {e}") from e

        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout: {e}")
            raise TimeoutError(f"Request to {endpoint} timed out") from e

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e.response.status_code}")
            try:
                error_data = e.response.json()
                raise HTTPError(f"HTTP {e.response.status_code}: {error_data.get('detail', error_data)}") from e
            except ValueError:
                raise HTTPError(f"HTTP {e.response.status_code}: {e.response.text}") from e

        except ValueError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise ValueError(f"Invalid JSON response from {endpoint}") from e

    def is_healthy(self) -> bool:
        """
        Check if the API service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            result = self._request("GET", "/health")
            return result.get("status") == "healthy"
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def health(self) -> Dict[str, Any]:
        """
        Get detailed health status.

        Returns:
            Dict with health status information:
            - status: "healthy", "degraded", or "unhealthy"
            - manager_loaded: Whether the prediction manager is loaded
            - current_time: Current simulation time
            - strategies: List of strategy names

        Raises:
            ConnectionError: If connection fails
            HTTPError: If HTTP status indicates error
        """
        return self._request("GET", "/health")

    def get_status(self) -> Dict[str, Any]:
        """
        Get detailed service status.

        Returns:
            Dict with service status information:
            - service_status: "healthy", "degraded", or "unhealthy"
            - prediction_service_loaded: Boolean
            - manager: Manager information (strategies, current_time, etc.)
            - available_dates: Date range information
            - error: Error message if unhealthy

        Raises:
            ConnectionError: If connection fails
            HTTPError: If HTTP status indicates error
        """
        return self._request("GET", "/status")

    def get_available_dates(self) -> List[str]:
        """
        Get list of dates with available predictions.

        Returns:
            List of date strings in YYYY-MM-DD format

        Raises:
            ConnectionError: If connection fails
            HTTPError: If HTTP status indicates error
        """
        result = self._request("GET", "/dates")
        return result.get("dates", [])

    def get_predictions(
        self,
        date: str,
        top_n: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get predictions for a specific date.

        Args:
            date: Target date in YYYY-MM-DD format
            top_n: Optional, return only top N predictions

        Returns:
            Dict with prediction data:
            - date: Query date
            - predictions: List of prediction dicts
              - instrument: Stock code
              - score: Prediction score
              - rank: Ranking (if available)
            - total_count: Total number of predictions
            - top_n: Top 10 predictions (legacy field)

        Raises:
            ConnectionError: If connection fails
            HTTPError: If HTTP status indicates error (404 if date not found)
            ValueError: If date format is invalid

        Example:
            >>> result = client.get_predictions("2025-01-15", top_n=5)
            >>> print(f"Top prediction: {result['predictions'][0]['instrument']}")
            >>> print(f"Score: {result['predictions'][0]['score']}")
        """
        params = {"date": date}
        if top_n is not None:
            params["top_n"] = top_n

        return self._request("GET", "/predictions", params=params)

    def batch_get_predictions(
        self,
        start_date: str,
        end_date: str,
        top_n: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get predictions for a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            top_n: Optional, return only top N predictions per date

        Returns:
            Dict with batch prediction data:
            - predictions: List of date predictions
              - date: Date string
              - predictions: List of predictions for this date
              - total_count: Number of predictions for this date
            - total_dates: Number of dates in result

        Raises:
            ConnectionError: If connection fails
            HTTPError: If HTTP status indicates error
            ValueError: If date format is invalid

        Example:
            >>> result = client.batch_get_predictions("2025-01-10", "2025-01-15")
            >>> for date_pred in result['predictions']:
            ...     print(f"{date_pred['date']}: {date_pred['total_count']} predictions")
        """
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        if top_n is not None:
            params["top_n"] = top_n

        return self._request("GET", "/batch", params=params)

    def get_top_predictions(
        self,
        date: str,
        n: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Convenience method to get top N predictions for a date.

        Args:
            date: Target date in YYYY-MM-DD format
            n: Number of top predictions to return

        Returns:
            List of prediction dicts sorted by score

        Raises:
            ConnectionError: If connection fails
            HTTPError: If HTTP status indicates error

        Example:
            >>> top_preds = client.get_top_predictions("2025-01-15", n=5)
            >>> for i, pred in enumerate(top_preds, 1):
            ...     print(f"{i}. {pred['instrument']}: {pred['score']:.4f}")
        """
        result = self.get_predictions(date, top_n=n)
        return result.get("predictions", [])

    def get_prediction_summary(
        self,
        date: str
    ) -> Dict[str, Any]:
        """
        Get summary statistics for predictions on a specific date.

        Args:
            date: Target date in YYYY-MM-DD format

        Returns:
            Dict with summary statistics:
            - date: Query date
            - total_count: Total number of predictions
            - score_stats: Score statistics
              - mean: Mean score
              - std: Standard deviation
              - min: Minimum score
              - max: Maximum score
            - top_10: Top 10 predictions

        Raises:
            ConnectionError: If connection fails
            HTTPError: If HTTP status indicates error

        Example:
            >>> summary = client.get_prediction_summary("2025-01-15")
            >>> print(f"Mean score: {summary['score_stats']['mean']:.4f}")
            >>> print(f"Score range: {summary['score_stats']['min']:.4f} to {summary['score_stats']['max']:.4f}")
        """
        import numpy as np

        result = self.get_predictions(date)
        predictions = result.get("predictions", [])

        if not predictions:
            return {
                "date": date,
                "total_count": 0,
                "score_stats": None,
                "top_10": []
            }

        scores = [p["score"] for p in predictions]

        return {
            "date": date,
            "total_count": len(predictions),
            "score_stats": {
                "mean": float(np.mean(scores)),
                "std": float(np.std(scores)),
                "min": float(np.min(scores)),
                "max": float(np.max(scores))
            },
            "top_10": predictions[:10]
        }

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class HTTPError(Exception):
    """HTTP error from API."""
    pass


class ConnectionError(Exception):
    """Connection error to API."""
    pass


class TimeoutError(Exception):
    """Request timeout error."""
    pass


# Convenience functions for quick access

def create_client(
    base_url: str = "http://localhost:8000",
    **kwargs
) -> StockPredictionClient:
    """
    Create a new API client.

    Args:
        base_url: Base URL of the API server
        **kwargs: Additional arguments passed to StockPredictionClient

    Returns:
        Configured StockPredictionClient instance

    Example:
        >>> client = create_client("http://localhost:8000", timeout=60)
        >>> predictions = client.get_predictions("2025-01-15")
    """
    return StockPredictionClient(base_url, **kwargs)


def quick_check(
    base_url: str = "http://localhost:8000"
) -> bool:
    """
    Quick health check of the API service.

    Args:
        base_url: Base URL of the API server

    Returns:
        True if service is healthy, False otherwise

    Example:
        >>> if quick_check():
        ...     print("Service is up!")
    """
    client = StockPredictionClient(base_url)
    try:
        return client.is_healthy()
    finally:
        client.close()
