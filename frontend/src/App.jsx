import {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import darknessIcon from './assets/energy/darkness.png';
import fightingIcon from './assets/energy/fighting.png';
import fireIcon from './assets/energy/fire.png';
import grassIcon from './assets/energy/grass.png';
import lightningIcon from './assets/energy/lightning.png';
import metalIcon from './assets/energy/metal.png';
import psychicIcon from './assets/energy/psychic.png';
import waterIcon from './assets/energy/water.png';
import {generateDeckQr} from './qr.js';
import {errorLabel, initialLanguage, STYLE_LABELS, styleLabel, translate} from './i18n.js';

const ENERGY_OPTIONS = [
  ['grass', '草系', 'Grass', grassIcon],
  ['fire', '火系', 'Fire', fireIcon],
  ['water', '水系', 'Water', waterIcon],
  ['lightning', '雷系', 'Lightning', lightningIcon],
  ['psychic', '超能系', 'Psychic', psychicIcon],
  ['fighting', '斗系', 'Fighting', fightingIcon],
  ['darkness', '恶系', 'Darkness', darknessIcon],
  ['metal', '钢系', 'Metal', metalIcon],
];

function App() {
  const [language, setLanguage] = useState(() => initialLanguage(
    window.localStorage.getItem('ptcgp-language'),
    window.navigator.language,
  ));
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState('');
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [energies, setEnergies] = useState([]);
  const [style, setStyle] = useState('auto');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [requestError, setRequestError] = useState('');
  const [result, setResult] = useState(null);
  const [qr, setQr] = useState({status: 'idle'});
  const [view, setView] = useState('original');
  const [copied, setCopied] = useState(false);
  const [qrCopied, setQrCopied] = useState(false);
  const copyTimer = useRef(null);
  const qrCopyTimer = useRef(null);
  const previewUrlRef = useRef('');
  const t = useCallback((key, values) => translate(language, key, values), [language]);

  useEffect(() => {
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
    window.localStorage.setItem('ptcgp-language', language);
  }, [language]);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/config', {cache: 'no-store', signal: controller.signal})
      .then(response => {
        if (!response.ok) throw new Error(t('config.readError'));
        return response.json();
      })
      .then(setConfig)
      .catch(error => {
        if (error.name !== 'AbortError') setConfigError(error.message);
      });
    return () => controller.abort();
  }, [t]);

  const chooseFile = useCallback(nextFile => {
    if (!nextFile) return;
    const suffix = nextFile.name.split('.').pop()?.toLowerCase();
    if (!['png', 'jpg', 'jpeg', 'webp'].includes(suffix)) {
      setMessage(t('file.unsupported'));
      return;
    }
    if (nextFile.size > 24 * 1024 * 1024) {
      setMessage(t('file.tooLarge'));
      return;
    }
    setFile(nextFile);
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = URL.createObjectURL(nextFile);
    setPreviewUrl(previewUrlRef.current);
    setResult(null);
    setQr({status: 'idle'});
    setRequestError('');
    setMessage('');
    setView('original');
  }, [t]);

  useEffect(() => () => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
  }, []);

  useEffect(() => {
    function handlePaste(event) {
      const imageItem = Array.from(event.clipboardData?.items || [])
        .find(item => item.type.startsWith('image/'));
      const pastedImage = imageItem?.getAsFile();
      if (!pastedImage) return;
      event.preventDefault();
      const suffix = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp',
      }[pastedImage.type];
      if (!suffix) {
        setMessage(t('file.clipboardUnsupported'));
        return;
      }
      const clipboardFile = new File(
        [pastedImage],
        `clipboard-${new Date().toISOString().replaceAll(':', '-').replaceAll('.', '-')}.${suffix}`,
        {type: pastedImage.type || 'image/png'},
      );
      chooseFile(clipboardFile);
    }

    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
  }, [chooseFile, t]);

  useEffect(() => () => {
    if (copyTimer.current) window.clearTimeout(copyTimer.current);
    if (qrCopyTimer.current) window.clearTimeout(qrCopyTimer.current);
  }, []);

  const recognizedUrl = useMemo(() => {
    const path = result?.artifacts?.['recognized.png'];
    return path ? `${path}?v=${Date.now()}` : '';
  }, [result]);

  const resultState = requestError
    ? {tone: 'error', symbol: '×', headline: t('result.requestFailed'), description: requestError}
    : result
      ? {
          tone: result.accepted ? 'success' : 'warning',
          symbol: result.accepted ? '✓' : '!',
          headline: result.accepted ? t('result.accepted') : t('result.review'),
          description: result.accepted
            ? (qr.status === 'ready'
                ? t('result.qrReady')
                : qr.status === 'error'
                  ? t('result.qrFailed')
                  : t('result.qrWorking'))
            : t('result.rejected'),
        }
      : busy
        ? {tone: 'idle', symbol: '···', headline: t('result.recognizing'), description: t('result.firstRun')}
        : {tone: 'idle', symbol: '—', headline: t('result.waiting'), description: t('result.waitingDescription')};

  function toggleEnergy(energy) {
    setEnergies(current => {
      if (current.includes(energy)) {
        setMessage('');
        return current.filter(item => item !== energy);
      }
      if (current.length === 3) {
        setMessage(t('energy.tooMany'));
        return current;
      }
      setMessage('');
      return [...current, energy];
    });
  }

  async function recognize() {
    if (!file || !energies.length || busy) return;
    setBusy(true);
    setMessage('');
    setRequestError('');
    setQr({status: 'idle'});
    try {
      const imageBase64 = await fileToBase64(file, t('file.readError'));
      const response = await fetch('/api/recognize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({filename: file.name, image_base64: imageBase64, energies, style}),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || t('request.failed'));
      setResult(payload);
      setView(payload.artifacts?.['recognized.png'] ? 'annotated' : 'original');
      if (payload.accepted) {
        if (payload.qr_error) {
          setQr({status: 'error', error: payload.qr_error});
        } else if (payload.qr_input) {
          setQr({status: 'loading'});
          try {
            const generated = await generateDeckQr(payload.qr_input);
            setQr({status: 'ready', ...generated, name: payload.qr_input.name});
          } catch (error) {
            setQr({
              status: 'error',
              error: error instanceof Error ? error.message : t('qr.failed'),
            });
          }
        } else {
          setQr({status: 'error', error: t('qr.missingInput')});
        }
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : t('request.failed');
      setRequestError(text);
      setMessage(text);
    } finally {
      setBusy(false);
    }
  }

  async function copyDeckText() {
    if (!result?.deck_text) return;
    try {
      await navigator.clipboard.writeText(result.deck_text);
      setCopied(true);
      if (copyTimer.current) window.clearTimeout(copyTimer.current);
      copyTimer.current = window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setMessage(t('copy.textFailed'));
    }
  }

  async function copyDeckCode() {
    if (qr.status !== 'ready') return;
    try {
      await navigator.clipboard.writeText(qr.deckCode);
      setQrCopied(true);
      if (qrCopyTimer.current) window.clearTimeout(qrCopyTimer.current);
      qrCopyTimer.current = window.setTimeout(() => setQrCopied(false), 1200);
    } catch {
      setMessage(t('copy.codeFailed'));
    }
  }

  const cacheKey = `?v=${result ? Date.now() : 0}`;
  const deckArtifact = result?.accepted ? result?.artifacts?.['deck.txt'] : result?.artifacts?.['deck.partial.txt'];

  return (
    <div className="app-shell">
      <Header
        language={language}
        onLanguage={() => setLanguage(current => current === 'zh' ? 'en' : 'zh')}
        t={t}
      />
      <main className="workspace">
        <SetupPanel
          file={file}
          energies={energies}
          style={style}
          busy={busy}
          message={message}
          onFile={chooseFile}
          onToggleEnergy={toggleEnergy}
          onStyle={setStyle}
          onRecognize={recognize}
          language={language}
          t={t}
        />
        <CanvasPanel
          previewUrl={previewUrl}
          recognizedUrl={recognizedUrl}
          view={view}
          busy={busy}
          result={result}
          onView={setView}
          language={language}
          t={t}
        />
        <ResultPanel
          result={result}
          state={resultState}
          copied={copied}
          qr={qr}
          qrCopied={qrCopied}
          cacheKey={cacheKey}
          deckArtifact={deckArtifact}
          onCopy={copyDeckText}
          onCopyDeckCode={copyDeckCode}
          language={language}
          t={t}
        />
      </main>
      <footer className={`status-bar ${config ? 'is-ready' : ''}`}>
        <span className="status-dot" />
        <span>{configError || t('privacy.local')}</span>
      </footer>
    </div>
  );
}

function Header({language, onLanguage, t}) {
  return (
    <header className="topbar">
      <div className="brand-lockup">
        <div className="app-mark" aria-hidden="true"><span /><span /></div>
      </div>
      <div className="active-workspace"><span>{t('app.title')}</span></div>
      <div className="header-actions">
        <button className="language-toggle" type="button" onClick={onLanguage} title={t('language.switch')} aria-label={t('language.switch')}>
          <span className={language === 'zh' ? 'is-active' : ''}>中</span>
          <i />
          <span className={language === 'en' ? 'is-active' : ''}>EN</span>
        </button>
      </div>
    </header>
  );
}

function PanelHeading({id, title, children, className = ''}) {
  return (
    <div className={`panel-heading ${className}`}>
      <h2 id={id}>{title}</h2>
      {children}
    </div>
  );
}

function SetupPanel({file, energies, style, busy, message, onFile, onToggleEnergy, onStyle, onRecognize, language, t}) {
  const [dragging, setDragging] = useState(false);
  return (
    <section className="game-panel setup-panel" aria-labelledby="setupTitle">
      <PanelHeading id="setupTitle" title={t('setup.title')} />
      <label
        className={`drop-zone ${dragging ? 'is-dragging' : ''} ${file ? 'has-file' : ''}`}
        aria-keyshortcuts="Control+V"
        onDragEnter={event => { event.preventDefault(); setDragging(true); }}
        onDragOver={event => event.preventDefault()}
        onDragLeave={event => { event.preventDefault(); setDragging(false); }}
        onDrop={event => { event.preventDefault(); setDragging(false); onFile(event.dataTransfer.files?.[0]); }}
      >
        <span className="upload-icon" aria-hidden="true"><span className="upload-mountain" /><span className="upload-sun" /></span>
        <strong>{file?.name || t('setup.drop')}</strong>
        <small>{file ? formatBytes(file.size) : t('setup.limit')}</small>
        <input type="file" accept="image/png,image/jpeg,image/webp" onChange={event => onFile(event.target.files?.[0])} />
      </label>
      <fieldset className="control-group energy-fieldset" disabled={busy}>
        <legend><span>{t('setup.energy')}</span><small>{energies.length ? t('setup.energySelected', {count: energies.length}) : t('setup.energyHint')}</small></legend>
        <div className="energy-grid">
          {ENERGY_OPTIONS.map(([value, zh, en, icon]) => (
            <button
              className={`energy-button energy-${value}`}
              type="button"
              key={value}
              aria-pressed={energies.includes(value)}
              aria-label={language === 'zh' ? zh : en}
              title={language === 'zh' ? zh : en}
              onClick={() => onToggleEnergy(value)}
            ><img src={icon} alt="" /></button>
          ))}
        </div>
      </fieldset>
      <div className="control-group">
        <label htmlFor="styleSelect"><span>{t('setup.style')}</span></label>
        <div className="select-shell">
          <select id="styleSelect" value={style} disabled={busy} onChange={event => onStyle(event.target.value)}>
            {Object.keys(STYLE_LABELS[language]).map(value => <option key={value} value={value}>{styleLabel(language, value)}</option>)}
          </select>
        </div>
      </div>
      <button className={`primary-button ${busy ? 'is-busy' : ''}`} type="button" disabled={busy || !file || !energies.length} onClick={onRecognize}>
        <span className="button-idle">{t('setup.start')}</span>
        <span className="button-busy"><i />{t('setup.working')}</span>
      </button>
      <p className="form-message" role="status">{message}</p>
    </section>
  );
}

function CanvasPanel({previewUrl, recognizedUrl, view, busy, result, onView, language, t}) {
  const hasImage = Boolean(previewUrl);
  const annotated = view === 'annotated' && Boolean(recognizedUrl);
  return (
    <section className="game-panel canvas-panel" aria-labelledby="canvasTitle">
      <PanelHeading id="canvasTitle" title={t('canvas.title')} className="canvas-heading">
        {recognizedUrl && <div className="view-switch">
          <button type="button" aria-pressed={!annotated} onClick={() => onView('original')}>{t('canvas.original')}</button>
          <button type="button" aria-pressed={annotated} onClick={() => onView('annotated')}>{t('canvas.annotated')}</button>
        </div>}
      </PanelHeading>
      <div className={`image-stage ${busy ? 'is-scanning' : ''}`} data-state={hasImage ? 'ready' : 'empty'}>
        {!hasImage && <div className="empty-stage">
          <div className="card-stack" aria-hidden="true"><span /><span /><span /></div>
          <strong>{t('canvas.emptyTitle')}</strong><p>{t('canvas.emptyDescription')}</p>
        </div>}
        {previewUrl && <img src={previewUrl} alt={t('canvas.previewAlt')} hidden={annotated} />}
        {recognizedUrl && <img src={recognizedUrl} alt={t('canvas.annotatedAlt')} hidden={!annotated} />}
        <div className="scan-effect" aria-hidden="true"><span /></div>
      </div>
      <div className="canvas-footer">
        <div className="legend">
          <span><i className="legend-ok" />{t('legend.reliable')}</span><span><i className="legend-alias" />{t('legend.alias')}</span>
          <span><i className="legend-warn" />{t('legend.count')}</span><span><i className="legend-error" />{t('legend.entity')}</span>
        </div>
        {result && <span>{styleLabel(language, result.detected_style)}</span>}
      </div>
    </section>
  );
}

function ResultPanel({result, state, copied, qr, qrCopied, cacheKey, deckArtifact, onCopy, onCopyDeckCode, language, t}) {
  const errors = result?.errors || [];
  const cards = result?.cards || [];
  return (
    <section className="game-panel result-panel" aria-labelledby="resultTitle">
      <PanelHeading id="resultTitle" title={t('results.title')} className="result-heading" />
      <div className="result-state" data-tone={state.tone}>
        <div className="result-count"><span className="result-symbol">{state.symbol}</span><strong>{result?.card_count ?? 0}<small> / 20</small></strong></div>
        <h3>{state.headline}</h3>
      </div>
      {errors.length > 0 && <div className="error-list"><strong>{t('results.failed')}</strong><div>{errors.map(error => errorLabel(language, error)).join(' · ')}</div></div>}
      {result?.accepted && <QrOutput qr={qr} copied={qrCopied} onCopy={onCopyDeckCode} t={t} />}
      {result && <details className="result-details">
        <summary><span>{t('results.details')}</span><small>{t('results.entries', {count: cards.length})}</small></summary>
        <div className="card-results">
          {cards.length ? cards.map((card, index) => (
            <div className={`card-row ${card.decision === 'accepted' ? '' : 'is-rejected'}`} key={card.slot_id || index}>
              <span className="card-row-index">{String(index + 1).padStart(2, '0')}</span>
              <span className="card-row-main"><strong>{card.selected_print || card.slot_id || t('results.unrecognized')}</strong></span>
              <span className="card-row-count">{card.count ? `×${card.count}` : '—'}</span>
            </div>
          )) : <div className="empty-results"><span>{t('results.none')}</span><small>{t('results.check')}</small></div>}
        </div>
        {result.deck_text && <div className="deck-output">
          <div className="deck-output-heading"><strong>{result.accepted ? 'deck.txt' : 'deck.partial.txt'}</strong><button className="text-button" type="button" onClick={onCopy}>{copied ? t('results.copied') : t('results.copy')}</button></div>
          <pre>{result.deck_text}</pre>
        </div>}
      </details>}
      <div className="result-actions">
        {result?.artifacts?.['recognition.json'] && <a className="secondary-button" href={`${result.artifacts['recognition.json']}${cacheKey}`} target="_blank" rel="noreferrer">{t('results.viewJson')}</a>}
        {deckArtifact && <a className="primary-button compact" href={`${deckArtifact}${cacheKey}`} download>{t('results.download', {filename: result.accepted ? 'deck.txt' : 'deck.partial.txt'})}</a>}
      </div>
    </section>
  );
}

function QrOutput({qr, copied, onCopy, t}) {
  const filename = `${sanitizeFilename(qr.name || 'ptcgp-deck')}-qr.png`;
  return (
    <div className="qr-output" data-status={qr.status} aria-live="polite">
      <div className="qr-output-heading">
        <strong>{t('qr.title')}</strong>
        <span>{qr.status === 'ready' ? t('qr.ready') : qr.status === 'error' ? t('qr.error') : t('qr.working')}</span>
      </div>
      {qr.status === 'ready' ? <div className="qr-ready">
        <img src={qr.dataUrl} alt={t('qr.alt', {name: qr.name || 'PTCGP'})} />
        <div className="qr-copy">
          <p>{t('qr.scanHint')}</p>
          <a className="primary-button compact" href={qr.dataUrl} download={filename}>{t('qr.download')}</a>
          <button className="secondary-button" type="button" onClick={onCopy}>{copied ? t('qr.copied') : t('qr.copy')}</button>
        </div>
      </div> : qr.status === 'error'
        ? <p className="qr-error">{qr.error}</p>
        : <div className="qr-loading"><i /><span>{t('qr.rendering')}</span></div>}
    </div>
  );
}

function fileToBase64(file, errorMessage) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(errorMessage));
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1]);
    reader.readAsDataURL(file);
  });
}

function formatBytes(bytes) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function sanitizeFilename(value) {
  return value.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '-').replace(/\s+/g, ' ').trim() || 'ptcgp-deck';
}

export default App;
