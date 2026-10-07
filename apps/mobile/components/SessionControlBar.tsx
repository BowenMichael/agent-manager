import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  Modal,
  ActivityIndicator,
} from 'react-native';
import { Theme } from '../constants/Theme';
import { injectContext, executeControlAction, updateParameters } from '../services/agentApi';

interface SessionControlBarProps {
  sessionId: string;
  status?: string;
  onMessageSent?: (text: string) => void;
  onActionTriggered?: (action: string) => void;
}

const AVAILABLE_MODELS = ['gemini-3.8-flash', 'gemini-2.5-pro', 'claude-3.5-sonnet'];
const EFFORT_LEVELS: ('low' | 'medium' | 'high')[] = ['low', 'medium', 'high'];

export const SessionControlBar: React.FC<SessionControlBarProps> = ({
  sessionId,
  status,
  onMessageSent,
  onActionTriggered,
}) => {
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedModel, setSelectedModel] = useState('gemini-3.8-flash');
  const [selectedEffort, setSelectedEffort] = useState<'low' | 'medium' | 'high'>('high');

  const handleSend = async () => {
    if (!inputText.trim() || loading) return;
    const textToSend = inputText.trim();
    setInputText('');
    setLoading(true);
    if (onMessageSent) onMessageSent(textToSend);
    await injectContext(sessionId, textToSend);
    setLoading(false);
  };

  const confirmAction = (action: 'stop' | 'resume' | 'restart' | 'complete', title: string) => {
    Alert.alert('Confirm Action', `Are you sure you want to ${title}?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Confirm',
        style: action === 'stop' ? 'destructive' : 'default',
        onPress: async () => {
          if (onActionTriggered) onActionTriggered(action);
          await executeControlAction(sessionId, action);
        },
      },
    ]);
  };

  const handleSaveParams = async () => {
    await updateParameters(sessionId, { model: selectedModel, effort: selectedEffort });
    setModalVisible(false);
  };

  return (
    <View style={styles.container}>
      <View style={styles.actionRow}>
        <TouchableOpacity style={[styles.actionBtn, styles.stopBtn]} onPress={() => confirmAction('stop', 'stop this agent session')}>
          <Text style={styles.actionBtnText}>⏹ Stop</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.actionBtn, styles.resumeBtn]} onPress={() => confirmAction('resume', 'resume execution')}>
          <Text style={styles.actionBtnText}>▶ Resume</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.actionBtn, styles.restartBtn]} onPress={() => confirmAction('restart', 'restart the agent task')}>
          <Text style={styles.actionBtnText}>🔄 Restart</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.actionBtn, styles.paramBtn]} onPress={() => setModalVisible(true)}>
          <Text style={styles.actionBtnText}>⚙️ Params</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          placeholder="Inject prompt or feedback..."
          placeholderTextColor={Theme.textSecondary}
          value={inputText}
          onChangeText={setInputText}
          multiline
        />
        <TouchableOpacity style={[styles.sendBtn, !inputText.trim() && styles.sendBtnDisabled]} onPress={handleSend} disabled={!inputText.trim() || loading}>
          {loading ? <ActivityIndicator size="small" color="#fff" /> : <Text style={styles.sendText}>Send</Text>}
        </TouchableOpacity>
      </View>

      <Modal visible={modalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Thinking Parameters</Text>
            <Text style={styles.sectionLabel}>Reasoning Model</Text>
            <View style={styles.pickerRow}>
              {AVAILABLE_MODELS.map((m) => (
                <TouchableOpacity key={m} style={[styles.choicePill, selectedModel === m && styles.choicePillActive]} onPress={() => setSelectedModel(m)}>
                  <Text style={[styles.choiceText, selectedModel === m && styles.choiceTextActive]}>{m.replace('gemini-', '').replace('claude-', '')}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={styles.sectionLabel}>Effort Tier</Text>
            <View style={styles.pickerRow}>
              {EFFORT_LEVELS.map((e) => (
                <TouchableOpacity key={e} style={[styles.choicePill, selectedEffort === e && styles.choicePillActive]} onPress={() => setSelectedEffort(e)}>
                  <Text style={[styles.choiceText, selectedEffort === e && styles.choiceTextActive]}>{e.toUpperCase()}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={styles.modalBtnRow}>
              <TouchableOpacity style={styles.modalCancelBtn} onPress={() => setModalVisible(false)}>
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalSaveBtn} onPress={handleSaveParams}>
                <Text style={styles.modalSaveText}>Save Parameters</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: Theme.surface,
    borderTopWidth: 1,
    borderTopColor: Theme.border,
    padding: 12,
  },
  actionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  actionBtn: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
  },
  stopBtn: { backgroundColor: '#EF444420', borderWidth: 1, borderColor: '#EF4444' },
  resumeBtn: { backgroundColor: '#10B98120', borderWidth: 1, borderColor: '#10B981' },
  restartBtn: { backgroundColor: '#38BDF820', borderWidth: 1, borderColor: '#38BDF8' },
  paramBtn: { backgroundColor: '#6366F120', borderWidth: 1, borderColor: '#6366F1' },
  actionBtnText: { fontSize: 12, fontWeight: '600', color: Theme.text },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Theme.surfaceSubtle,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: Theme.border,
  },
  input: {
    flex: 1,
    color: Theme.text,
    fontSize: 14,
    minHeight: 36,
    maxHeight: 90,
  },
  sendBtn: {
    backgroundColor: Theme.primary,
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 6,
    marginLeft: 8,
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },
  sendText: {
    color: '#090D16',
    fontWeight: '700',
    fontSize: 13,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    width: '100%',
    backgroundColor: Theme.surface,
    borderRadius: 12,
    padding: 20,
    borderWidth: 1,
    borderColor: Theme.border,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: Theme.text, marginBottom: 14 },
  sectionLabel: { fontSize: 12, fontWeight: '600', color: Theme.textSecondary, marginTop: 10, marginBottom: 6 },
  pickerRow: { flexDirection: 'row', gap: 8 },
  choicePill: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: Theme.surfaceSubtle,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Theme.border,
  },
  choicePillActive: { borderColor: Theme.primary, backgroundColor: '#38BDF820' },
  choiceText: { fontSize: 12, color: Theme.textMuted },
  choiceTextActive: { color: Theme.primary, fontWeight: '700' },
  modalBtnRow: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 20, gap: 10 },
  modalCancelBtn: { paddingVertical: 8, paddingHorizontal: 14 },
  modalCancelText: { color: Theme.textMuted },
  modalSaveBtn: { backgroundColor: Theme.primary, paddingVertical: 8, paddingHorizontal: 16, borderRadius: 6 },
  modalSaveText: { color: '#090D16', fontWeight: '700' },
});
