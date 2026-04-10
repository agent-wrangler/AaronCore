// AwarenessManager compatibility stub.
// The old awareness-ball UI has been retired, but other chat scripts still
// call these methods. Keep a tiny no-op facade instead of leaving half-removed
// polling code around.
var AwarenessManager = (function () {
  var STORAGE_KEY = 'awareness_balls';

  function _clearStorage() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
  }

  function _clearBar() {
    var bar = document.getElementById('awarenessBar');
    if (!bar) return;
    bar.innerHTML = '';
    bar.classList.remove('has-balls');
    bar.style.display = 'none';
  }

  function _retireAwarenessUi() {
    _clearStorage();
    _clearBar();
  }

  function init() {
    _retireAwarenessUi();
  }

  function handleEvent() {}

  function handleEvents() {}

  function startPolling() {}

  function stopPolling() {}

  function clearAllBalls() {
    _retireAwarenessUi();
  }

  return {
    init: init,
    handleEvent: handleEvent,
    handleEvents: handleEvents,
    startPolling: startPolling,
    stopPolling: stopPolling,
    clearAllBalls: clearAllBalls,
  };
})();
