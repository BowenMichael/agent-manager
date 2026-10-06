/**
 * Push Notification Hook for Expo Mobile Client.
 * Handles permission requests, Expo Push Token registration, and deep linking navigation.
 * Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
 */

import { useState, useEffect, useRef } from 'react';
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { useRouter } from 'expo-router';
import { API_BASE_URL } from '../constants/Config';

export interface PushNotificationState {
  expoPushToken?: string;
  notification?: Notifications.Notification;
  error?: Error;
}

export function usePushNotifications(): PushNotificationState {
  const [expoPushToken, setExpoPushToken] = useState<string | undefined>();
  const [notification, setNotification] = useState<Notifications.Notification | undefined>();
  const [error, setError] = useState<Error | undefined>();
  const router = useRouter();

  const notificationListener = useRef<Notifications.Subscription>();
  const responseListener = useRef<Notifications.Subscription>();

  useEffect(() => {
    registerForPushNotificationsAsync()
      .then((token) => {
        if (token) {
          setExpoPushToken(token);
          sendTokenToBackend(token);
        }
      })
      .catch((err) => setError(err));

    notificationListener.current = Notifications.addNotificationReceivedListener((notif) => {
      setNotification(notif);
    });

    responseListener.current = Notifications.addNotificationResponseReceivedListener((response) => {
      handleNotificationTap(response, router);
    });

    return () => {
      if (notificationListener.current) {
        Notifications.removeNotificationSubscription(notificationListener.current);
      }
      if (responseListener.current) {
        Notifications.removeNotificationSubscription(responseListener.current);
      }
    };
  }, []);

  return { expoPushToken, notification, error };
}

export async function registerForPushNotificationsAsync(): Promise<string | undefined> {
  if (!Device.isDevice && Platform.OS !== 'web') {
    return undefined;
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    return undefined;
  }

  const tokenData = await Notifications.getExpoPushTokenAsync();
  return tokenData.data;
}

export async function sendTokenToBackend(pushToken: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/notifications/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        push_token: pushToken,
        device_name: `${Device.modelName || 'Mobile'} (${Platform.OS})`,
        platform: Platform.OS,
      }),
    });
    return response.ok;
  } catch (err) {
    return false;
  }
}

export function handleNotificationTap(
  response: Notifications.NotificationResponse,
  router: ReturnType<typeof useRouter>
) {
  const data = response.notification.request.content.data;
  if (data && data.session_id) {
    router.push(`/session/${data.session_id}`);
  }
}
