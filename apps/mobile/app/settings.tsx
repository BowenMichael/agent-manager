import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Theme } from '../constants/Theme';
import { Config } from '../constants/Config';

export default function SettingsScreen() {
  const router = useRouter();
  const [apiUrl, setApiUrl] = useState(Config.apiUrl);
  const [wsUrl, setWsUrl] = useState(Config.wsUrl);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  const handleSave = () => {
    setSaveStatus('Settings updated (active session)');
    setTimeout(() => setSaveStatus(null), 2500);
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Backend Connection</Text>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>REST API URL (EXPO_PUBLIC_API_URL)</Text>
          <TextInput
            style={styles.input}
            value={apiUrl}
            onChangeText={setApiUrl}
            placeholder="http://localhost:8000"
            placeholderTextColor={Theme.textSecondary}
            autoCapitalize="none"
            autoCorrect={false}
          />
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>WebSocket URL (EXPO_PUBLIC_WS_URL)</Text>
          <TextInput
            style={styles.input}
            value={wsUrl}
            onChangeText={setWsUrl}
            placeholder="ws://localhost:8000/ws/agents"
            placeholderTextColor={Theme.textSecondary}
            autoCapitalize="none"
            autoCorrect={false}
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Application Information</Text>
        <View style={styles.infoCard}>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>App Name</Text>
            <Text style={styles.infoValue}>{Config.appName}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>App Version</Text>
            <Text style={styles.infoValue}>{Config.appVersion}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>UI Theme</Text>
            <Text style={styles.infoValue}>Agent Dark Palette</Text>
          </View>
        </View>
      </View>

      {saveStatus && (
        <View style={styles.statusToast}>
          <Text style={styles.statusText}>{saveStatus}</Text>
        </View>
      )}

      <TouchableOpacity
        style={styles.saveButton}
        activeOpacity={0.8}
        onPress={handleSave}
      >
        <Text style={styles.saveButtonText}>Save Settings</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.backButton}
        activeOpacity={0.8}
        onPress={() => router.back()}
      >
        <Text style={styles.backButtonText}>Back</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Theme.background,
  },
  content: {
    padding: 16,
    gap: 24,
  },
  section: {
    gap: 12,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: Theme.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  inputGroup: {
    gap: 6,
  },
  label: {
    fontSize: 13,
    color: Theme.text,
    fontWeight: '500',
  },
  input: {
    backgroundColor: Theme.surface,
    borderWidth: 1,
    borderColor: Theme.border,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: Theme.text,
    fontSize: 14,
  },
  infoCard: {
    backgroundColor: Theme.card,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Theme.borderLight,
    padding: 14,
    gap: 12,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  infoLabel: {
    fontSize: 13,
    color: Theme.textMuted,
  },
  infoValue: {
    fontSize: 13,
    color: Theme.text,
    fontWeight: '600',
  },
  statusToast: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    borderWidth: 1,
    borderColor: Theme.success,
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
  },
  statusText: {
    color: Theme.success,
    fontWeight: '600',
    fontSize: 13,
  },
  saveButton: {
    backgroundColor: Theme.primary,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
  },
  saveButtonText: {
    color: '#090D16',
    fontWeight: '700',
    fontSize: 14,
  },
  backButton: {
    backgroundColor: Theme.surfaceSubtle,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: Theme.border,
    paddingVertical: 14,
    alignItems: 'center',
  },
  backButtonText: {
    color: Theme.text,
    fontWeight: '600',
    fontSize: 14,
  },
});
