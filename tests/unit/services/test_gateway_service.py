"""Tests for RequestSubmissionService and gateway endpoints."""
from unittest.mock import MagicMock

import pytest

from src.shared.objects.requests.processed_request import ProcessedRequest
from src.shared.objects.enums.request_stage import RequestStage
from src.shared.objects.enums.request_status import RequestStatus
from src.shared.objects.requests.query_request import QueryRequest
from src.services.gateway.request_submission_service import RequestSubmissionService


class TestRequestSubmissionService:
    @pytest.fixture
    def service(self, mock_state_repository, mock_message_publisher):
        return RequestSubmissionService(
            state_repository=mock_state_repository,
            message_publisher=mock_message_publisher,
            query_topic="query",
        )

    def test_submit_request_returns_accepted(self, service, sample_query_request):
        response = service.submit_request(sample_query_request)

        assert response.status == RequestStatus.Accepted
        assert response.request_id is not None
        assert len(response.request_id) == 36  # UUID format

    def test_submit_request_creates_state(self, service, mock_state_repository, sample_query_request):
        response = service.submit_request(sample_query_request)

        mock_state_repository.create.assert_called_once()
        call_args = mock_state_repository.create.call_args
        assert call_args[0][0] == response.request_id

    def test_submit_request_publishes_message(self, service, mock_message_publisher, sample_query_request):
        response = service.submit_request(sample_query_request)

        mock_message_publisher.publish.assert_called_once()
        call_args = mock_message_publisher.publish.call_args
        assert call_args[0][0] == "query"  # topic name

    def test_get_request_status_found(self, service, mock_state_repository, sample_query_request):
        state_data = ProcessedRequest(
            request_id="test-id",
            query_request=sample_query_request,
            stage=RequestStage.Completed,
        ).model_dump(mode="json")
        mock_state_repository.get.return_value = state_data

        result = service.get_request_status("test-id")
        assert result.stage == RequestStage.Completed

    def test_get_request_status_not_found(self, service, mock_state_repository):
        mock_state_repository.get.return_value = None

        with pytest.raises(KeyError):
            service.get_request_status("nonexistent")
