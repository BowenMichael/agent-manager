import { useState, useRef, useCallback } from 'react'

export interface UseSpeechRecognitionReturn {
  isListening: boolean
  startListening: (onTranscript: (text: string) => void, onError: (err: string) => void) => void
  stopListening: () => void
  toggleListening: (onTranscript: (text: string) => void, onError: (err: string) => void) => void
}

export function useSpeechRecognition(): UseSpeechRecognitionReturn {
  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef<any>(null)

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch (e) {
        // Ignore errors during abort
      }
      recognitionRef.current = null
    }
    setIsListening(false)
  }, [])

  const startListening = useCallback(
    (onTranscript: (text: string) => void, onError: (err: string) => void) => {
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

      if (!SpeechRecognition) {
        onError('Speech recognition is not supported in this browser. Please type directly.')
        return
      }

      try {
        const recognition = new SpeechRecognition()
        recognition.continuous = true
        recognition.interimResults = true
        recognition.lang = 'en-US'

        recognition.onstart = () => setIsListening(true)

        recognition.onresult = (event: any) => {
          let currentTranscript = ''
          for (let i = 0; i < event.results.length; i++) {
            currentTranscript += event.results[i][0].transcript + ' '
          }
          onTranscript(currentTranscript.trim())
        }

        recognition.onerror = (event: any) => {
          if (event.error === 'not-allowed') {
            onError('Microphone access was denied. Please allow microphone permissions or type below.')
          } else {
            onError(`Speech error: ${event.error}`)
          }
          setIsListening(false)
        }

        recognition.onend = () => setIsListening(false)

        recognitionRef.current = recognition
        recognition.start()
      } catch (err: any) {
        onError(err.message || 'Could not start speech recognition.')
        setIsListening(false)
      }
    },
    []
  )

  const toggleListening = useCallback(
    (onTranscript: (text: string) => void, onError: (err: string) => void) => {
      if (isListening) {
        stopListening()
      } else {
        startListening(onTranscript, onError)
      }
    },
    [isListening, startListening, stopListening]
  )

  return { isListening, startListening, stopListening, toggleListening }
}
