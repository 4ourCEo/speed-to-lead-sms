"""Tests for owner notification service"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from app.services.owner_notifications import (
    send_owner_notification,
    send_slack_notification,
    send_email_notification,
    should_skip_sms
)


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    with patch('app.services.owner_notifications.settings') as mock:
        mock.slack_webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK"
        mock.owner_notify_email = "owner@example.com"
        mock.resend_api_key = "re_test_key"
        mock.resend_domain = "resend.dev"
        mock.owner_callback_phone = "+15551234567"
        mock.interim_no_sms = False
        mock.skip_caller_sms = False
        yield mock


@pytest.fixture
def lead_data():
    """Sample lead data for testing"""
    return {
        'caller_number': '+15559876543',
        'tracking_number': '+15551234567',
        'shop_name': 'Test HVAC',
        'timestamp': datetime(2024, 9, 12, 10, 30, 0),
        'lead_id': 'test-lead-123',
        'call_sid': 'CA1234567890'
    }


def test_should_skip_sms_false_by_default(mock_settings):
    """Test that SMS is not skipped by default"""
    mock_settings.interim_no_sms = False
    mock_settings.skip_caller_sms = False
    assert should_skip_sms() is False


def test_should_skip_sms_with_interim_no_sms(mock_settings):
    """Test that SMS is skipped when INTERIM_NO_SMS is true"""
    mock_settings.interim_no_sms = True
    mock_settings.skip_caller_sms = False
    assert should_skip_sms() is True


def test_should_skip_sms_with_skip_caller_sms(mock_settings):
    """Test that SMS is skipped when SKIP_CALLER_SMS is true"""
    mock_settings.interim_no_sms = False
    mock_settings.skip_caller_sms = True
    assert should_skip_sms() is True


@patch('app.services.owner_notifications.requests.post')
def test_send_slack_notification_success(mock_post, mock_settings, lead_data):
    """Test successful Slack notification"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    
    result = send_slack_notification(
        caller_number=lead_data['caller_number'],
        tracking_number=lead_data['tracking_number'],
        shop_name=lead_data['shop_name'],
        formatted_time='2024-09-12 10:30 AM UTC',
        lead_id=lead_data['lead_id']
    )
    
    assert result is True
    mock_post.assert_called_once()
    
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://hooks.slack.com/services/TEST/WEBHOOK"
    
    payload = call_args[1]['json']
    assert 'blocks' in payload
    assert 'text' in payload
    assert lead_data['caller_number'] in payload['text']


@patch('app.services.owner_notifications.requests.post')
def test_send_slack_notification_failure(mock_post, mock_settings, lead_data):
    """Test Slack notification failure"""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = 'Internal Server Error'
    mock_post.return_value = mock_response
    
    result = send_slack_notification(
        caller_number=lead_data['caller_number'],
        tracking_number=lead_data['tracking_number'],
        shop_name=lead_data['shop_name'],
        formatted_time='2024-09-12 10:30 AM UTC',
        lead_id=lead_data['lead_id']
    )
    
    assert result is False


@patch('app.services.owner_notifications.requests.post')
def test_send_email_notification_success(mock_post, mock_settings, lead_data):
    """Test successful email notification"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    
    result = send_email_notification(
        caller_number=lead_data['caller_number'],
        tracking_number=lead_data['tracking_number'],
        shop_name=lead_data['shop_name'],
        formatted_time='2024-09-12 10:30 AM UTC',
        lead_id=lead_data['lead_id']
    )
    
    assert result is True
    mock_post.assert_called_once()
    
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.resend.com/emails"
    
    headers = call_args[1]['headers']
    assert headers['Authorization'] == 'Bearer re_test_key'
    
    payload = call_args[1]['json']
    assert payload['to'] == ['owner@example.com']
    assert lead_data['shop_name'] in payload['subject']
    assert lead_data['caller_number'] in payload['html']
    assert lead_data['caller_number'] in payload['text']


@patch('app.services.owner_notifications.requests.post')
def test_send_email_notification_failure(mock_post, mock_settings, lead_data):
    """Test email notification failure"""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = 'Bad Request'
    mock_post.return_value = mock_response
    
    result = send_email_notification(
        caller_number=lead_data['caller_number'],
        tracking_number=lead_data['tracking_number'],
        shop_name=lead_data['shop_name'],
        formatted_time='2024-09-12 10:30 AM UTC',
        lead_id=lead_data['lead_id']
    )
    
    assert result is False


def test_send_email_notification_no_api_key(lead_data):
    """Test email notification when no API key is configured"""
    with patch('app.services.owner_notifications.settings') as mock_settings:
        mock_settings.resend_api_key = None
        mock_settings.owner_notify_email = "owner@example.com"
        
        result = send_email_notification(
            caller_number=lead_data['caller_number'],
            tracking_number=lead_data['tracking_number'],
            shop_name=lead_data['shop_name'],
            formatted_time='2024-09-12 10:30 AM UTC',
            lead_id=lead_data['lead_id']
        )
        
        assert result is False


def test_send_email_notification_no_email(lead_data):
    """Test email notification when no email is configured"""
    with patch('app.services.owner_notifications.settings') as mock_settings:
        mock_settings.resend_api_key = "re_test_key"
        mock_settings.owner_notify_email = None
        
        result = send_email_notification(
            caller_number=lead_data['caller_number'],
            tracking_number=lead_data['tracking_number'],
            shop_name=lead_data['shop_name'],
            formatted_time='2024-09-12 10:30 AM UTC',
            lead_id=lead_data['lead_id']
        )
        
        assert result is False


@patch('app.services.owner_notifications.send_slack_notification')
@patch('app.services.owner_notifications.send_email_notification')
def test_send_owner_notification_both_channels(mock_email, mock_slack, mock_settings, lead_data):
    """Test sending owner notification via both Slack and email"""
    mock_slack.return_value = True
    mock_email.return_value = True
    
    result = send_owner_notification(
        caller_number=lead_data['caller_number'],
        tracking_number=lead_data['tracking_number'],
        shop_name=lead_data['shop_name'],
        timestamp=lead_data['timestamp'],
        lead_id=lead_data['lead_id'],
        call_sid=lead_data['call_sid']
    )
    
    assert result['slack_sent'] is True
    assert result['email_sent'] is True
    assert len(result['errors']) == 0
    
    mock_slack.assert_called_once()
    mock_email.assert_called_once()


@patch('app.services.owner_notifications.send_slack_notification')
@patch('app.services.owner_notifications.send_email_notification')
def test_send_owner_notification_slack_only(mock_email, mock_slack, lead_data):
    """Test sending owner notification via Slack only"""
    with patch('app.services.owner_notifications.settings') as mock_settings:
        mock_settings.slack_webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK"
        mock_settings.owner_notify_email = None
        mock_settings.resend_api_key = None
        mock_settings.owner_callback_phone = "+15551234567"
        
        mock_slack.return_value = True
        
        result = send_owner_notification(
            caller_number=lead_data['caller_number'],
            tracking_number=lead_data['tracking_number'],
            shop_name=lead_data['shop_name'],
            timestamp=lead_data['timestamp'],
            lead_id=lead_data['lead_id'],
            call_sid=lead_data['call_sid']
        )
        
        assert result['slack_sent'] is True
        assert result['email_sent'] is False
        mock_slack.assert_called_once()
        mock_email.assert_not_called()


@patch('app.services.owner_notifications.send_slack_notification')
@patch('app.services.owner_notifications.send_email_notification')
def test_send_owner_notification_handles_exceptions(mock_email, mock_slack, mock_settings, lead_data):
    """Test that send_owner_notification handles exceptions gracefully"""
    mock_slack.side_effect = Exception("Slack API error")
    mock_email.return_value = True
    
    result = send_owner_notification(
        caller_number=lead_data['caller_number'],
        tracking_number=lead_data['tracking_number'],
        shop_name=lead_data['shop_name'],
        timestamp=lead_data['timestamp'],
        lead_id=lead_data['lead_id'],
        call_sid=lead_data['call_sid']
    )
    
    assert result['slack_sent'] is False
    assert result['email_sent'] is True
    assert len(result['errors']) == 1
    assert 'Slack error' in result['errors'][0]


def test_slack_notification_uses_callback_phone(mock_settings, lead_data):
    """Test that Slack notification uses OWNER_CALLBACK_PHONE if set"""
    with patch('app.services.owner_notifications.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        mock_settings.owner_callback_phone = "+15551111111"
        
        send_slack_notification(
            caller_number=lead_data['caller_number'],
            tracking_number=lead_data['tracking_number'],
            shop_name=lead_data['shop_name'],
            formatted_time='2024-09-12 10:30 AM UTC',
            lead_id=lead_data['lead_id']
        )
        
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        
        payload_str = str(payload)
        assert '+15551111111' in payload_str


def test_email_notification_uses_callback_phone(mock_settings, lead_data):
    """Test that email notification uses OWNER_CALLBACK_PHONE if set"""
    with patch('app.services.owner_notifications.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        mock_settings.owner_callback_phone = "+15551111111"
        
        send_email_notification(
            caller_number=lead_data['caller_number'],
            tracking_number=lead_data['tracking_number'],
            shop_name=lead_data['shop_name'],
            formatted_time='2024-09-12 10:30 AM UTC',
            lead_id=lead_data['lead_id']
        )
        
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        
        assert '+15551111111' in payload['html']
        assert '+15551111111' in payload['text']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
