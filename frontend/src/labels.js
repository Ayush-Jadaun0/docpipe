export const STAGES = {
  queued: 'Waiting in line',
  reading: 'Reading the file',
  ocr: 'Reading scanned text',
  classifying: 'Identifying the document type',
  extracting: 'Extracting fields',
  validating: 'Checking the values',
  retrying: 'Re-checking doubtful values',
  locating: 'Finding values on the page',
  done: 'Done',
}

// icon + word, so status never depends on colour alone
export const STATUS = {
  verified: { label: 'Verified', tone: 'ok', icon: '✓' },
  corrected: { label: 'Corrected', tone: 'ok', icon: '✎' },
  unverified: { label: 'Unverified', tone: 'warn', icon: '?' },
  invalid: { label: 'Invalid', tone: 'bad', icon: '!' },
  missing: { label: 'Not found', tone: 'mute', icon: '–' },
}

export const humanize = (s) => {
  const t = String(s).replaceAll('_', ' ')
  return t.charAt(0).toUpperCase() + t.slice(1)
}

export const SUGGEST = {
  invoice: ['What is the total amount?', 'Who is the vendor?', 'When is payment due?'],
  receipt: ['What is the total amount?', 'Which shop issued this receipt?', 'What was the date of purchase?'],
  id_card: ['What is the name on the card?', 'What is the date of birth?'],
  resume: ['Summarize this resume in three sentences.', 'What skills are listed?', 'Where did the candidate study?'],
  other: ['Summarize this document in three sentences.', 'What are the key points?', 'Are any dates or deadlines mentioned?'],
}
export const SUGGEST_ALL = [
  'Which invoice has the highest total?',
  'List every vendor and its total.',
  'Which documents need review?',
]
