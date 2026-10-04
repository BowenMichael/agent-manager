import React from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Theme } from '../constants/Theme';

export default function RootLayout() {
  return (
    <SafeAreaProvider style={{ backgroundColor: Theme.background }}>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: {
            backgroundColor: Theme.headerBackground,
          },
          headerTintColor: Theme.text,
          headerTitleStyle: {
            fontWeight: '700',
          },
          headerShadowVisible: false,
          contentStyle: {
            backgroundColor: Theme.background,
          },
        }}
      >
        <Stack.Screen
          name="index"
          options={{
            title: 'Agent Manager',
          }}
        />
        <Stack.Screen
          name="session/[id]"
          options={{
            title: 'Session Details',
            headerBackTitle: 'Sessions',
          }}
        />
        <Stack.Screen
          name="settings"
          options={{
            title: 'Settings',
            headerBackTitle: 'Back',
          }}
        />
      </Stack>
    </SafeAreaProvider>
  );
}
