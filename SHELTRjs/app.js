const bitcore = require('ghost-bitcore-lib');
const Mnemonic = require('bitcore-mnemonic');
const Message = require('ghost-bitcore-message');

var bech32 = require('bech32-buffer');


signMessage = function(privKey, msg){
  var privateKey = new bitcore.PrivateKey(privKey);
  var message = new Message(msg);

  var signature = message.sign(privateKey);

  console.log(signature);
}

address = function(inVal) {
    var value = Buffer.from(inVal);
    var hash = bitcore.crypto.Hash.sha256(value);
    var bn = bitcore.crypto.BN.fromBuffer(hash);

    var address = new bitcore.PrivateKey(bn).toAddress();

    var thing = address.toString();
    return thing
};

getXandY = function (pubKey) {

  var publicKey = new bitcore.PublicKey(pubKey);
  var point = publicKey.point;
  var x = point.getX();
  var y = point.getY();
  
  return { x, y };
  
}

getMnemonic = function(){

    var code = new Mnemonic(Mnemonic.Words.ENGLISH);
    var words = code.toString();    

    return {"words": words}

};

isValidMnemonic = function(words) {

    return Mnemonic.isValid(words);
};

importMnemonic = function(words) {

    var code = new Mnemonic(words);    
    var x = code.toHDPrivateKey();
    var hdPublicKey = x.hdPublicKey;

    var derived = deriveAccount(x)

    return {"xpriv": x, "xpub": hdPublicKey, "words": words, "derived_xpriv": derived.derived_xpriv, "derived_xpub": derived.derived_xpub,
    "derived_xpriv_change": derived.derived_xpriv_change, "derived_xpub_change": derived.derived_xpub_change}

};

deriveAccount = function (xpriv){
  var hdPrivateKey = new bitcore.HDPrivateKey(xpriv);

  var derivedXpriv = hdPrivateKey.deriveChild("m/44'/531'/0'").deriveChild(0);
  var derivedXpriv_change = hdPrivateKey.deriveChild("m/44'/531'/0'").deriveChild(1);
  
  return { "derived_xpriv":  derivedXpriv, "derived_xpub": derivedXpriv.hdPublicKey,
  "derived_xpriv_change": derivedXpriv_change, "derived_xpub_change": derivedXpriv_change.hdPublicKey}
  
}

getAddrFromXpriv = function(xpriv, index) {
    var hdPrivateKey = new bitcore.HDPrivateKey(xpriv);
    var hdPublicKey = hdPrivateKey.hdPublicKey;
    //try {
    //new bitcore.HDPublicKey();
    //} catch(e) {
    //console.log("Can't generate a public key without a private key");
    //}

    // var address = new bitcore.Address(hdPublicKey.publicKey, bitcore.Networks.livenet);
    var derivedAddress = new bitcore.Address(hdPublicKey.deriveChild(index).publicKey, bitcore.Networks.livenet);
    //var derivedPrivAddress = hdPrivateKey.derive(index).privateKey.toWIF(); // see deprecation warning for derive

    return derivedAddress
};

getAddrFromXpub = function(xpub, index, is256=false) {
    var hdPublicKey = new bitcore.HDPublicKey(xpub);
    var derivedAddress = new bitcore.Address.fromPublicKey(hdPublicKey.deriveChild(index).publicKey, bitcore.Networks.livenet, is256).toString();
    
    return derivedAddress
};


buildColdstakeScript = function(spendAddr, stakeAddr) {

    var script = bitcore.Script.buildPublicKeyHashOut256(spendAddr, stakeAddr);
    return script.toHex()
};


getPrivKeyFromXpriv = function(xpriv, index) {
    var hdPrivateKey = new bitcore.HDPrivateKey(xpriv);

    var derivedPrivAddress = hdPrivateKey.deriveChild(index).privateKey.toWIF(); // see deprecation warning for derive

    return derivedPrivAddress
};


getPubKeyFromXpub = function(xpub, index) {
  var hdPublicKey = new bitcore.HDPublicKey(xpub);
  var derivedAddress = hdPublicKey.deriveChild(index).publicKey.toString();
  
  return derivedAddress
};

const dbName = 'SHELTRdb';
const objectStoreName = 'SHELTRObjectStore';
const dbVersion = 1;

const openRequest = indexedDB.open(dbName, dbVersion);

openRequest.onupgradeneeded = function(event) {
  const db = event.target.result;
  db.createObjectStore(objectStoreName);
};


storeData = function(key, value) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(dbName);

    request.onsuccess = function(event) {
      const db = event.target.result;
      const transaction = db.transaction([objectStoreName], 'readwrite');
      const objectStore = transaction.objectStore(objectStoreName);

      const putRequest = objectStore.put(value, key);

      putRequest.onsuccess = function() {
        resolve(true);
      };

      putRequest.onerror = function() {
        reject(Error("Error storing data"));
      };

      transaction.oncomplete = function() {
        db.close();
      };
    };

    request.onerror = function() {
      reject(Error("Error opening database"));
    };
  });
};

getData = function(key) {
  const request = indexedDB.open(dbName);
  
  return new Promise(function(resolve, reject) {
    request.onsuccess = function(event) {
      const db = event.target.result;
      const transaction = db.transaction([objectStoreName], 'readonly');
      const objectStore = transaction.objectStore(objectStoreName);
      
      const getRequest = objectStore.get(key);
      
      getRequest.onsuccess = function(event) {
        const value = getRequest.result;
        if (typeof value !== 'undefined') {
          resolve(value);
        } else {
          resolve(null);
        }
        db.close();
      };
      
      getRequest.onerror = function(event) {
        reject(event.target.error);
        db.close();
      };
    };
    
    request.onerror = function(event) {
      reject(event.target.error);
    };
  });
};



generateTx = function( utxos, changeAddress, toAddress, privateKey, amount, fee, stakeAddr=false) {
    const tx = bitcore.Transaction();
    tx.from(utxos);
    tx.to(toAddress, amount);

    if (stakeAddr){
      tx.change(changeAddress, stakeAddr);
    } else {
      tx.change(changeAddress);
    }
    tx.fee(fee);
    try {
      tx.sign(privateKey);
      //tx.serialize();
    } catch (err) {
      throw new Error(`Could not sign & serialize transaction: ${err}`);
    }
    return tx;
  };

generateTxScript = function( utxos, changeAddress, scriptArray, privateKey, fee, stakeAddr ) {
  const tx = new bitcore.Transaction();
  tx.from(utxos);
  
  scriptArray.forEach(([outScript, amount]) => {
    tx.addOutput(bitcore.Transaction.Output({
      script: outScript,
      satoshis: amount
    }));
  });
  
  tx.change(changeAddress, stakeAddr);
  tx.fee(fee);
  try {
    tx.sign(privateKey);
    //tx.serialize();
  } catch (err) {
    throw new Error(`Could not sign & serialize transaction: ${err}`);
  }
  return tx;
};


estimateFee = function(utxos, changeAddress, toAddress, amount) {
    const tx = bitcore.Transaction();
    tx.from(utxos);
    tx.to(toAddress, amount);
    tx.change(changeAddress);

    return tx.getFee();

};

estimateFeeScript = function(utxos, changeAddress, scriptArray) {
  const tx = bitcore.Transaction();
  tx.from(utxos);
  scriptArray.forEach(([outScript, amount]) => {
    tx.addOutput(bitcore.Transaction.Output({
      script: outScript,
      satoshis: amount
    }));
  });
  tx.change(changeAddress);

  return tx.getFee();

};


let disconnectFn;

txMonitor = function(urls) {
  eventToListenTo = 'room_message'
  room = {"username": Math.floor(Math.random() * 100000000).toString(), "room": "tx"}

  var socket;
  var connected = false;

  function connect(urlIndex) {
    if (urlIndex >= urls.length) {
      return;
    }

    //console.log('Trying to connect to ' + urls[urlIndex]);
    socket = io(urls[urlIndex]);
    socket.on('connect', function() {
      //console.log('Connected to ' + urls[urlIndex]);
      if (!connected) {
        // Join the room.
        socket.emit('join', room, function(response) {
          //console.log('Joined room', response);
        });
        connected = true;
      }
    });
    socket.on(eventToListenTo, function(data) {
      //console.log('Received message', data);
      pything = pyscript.runtime.globals.get('newTx');
      pything(data);
    });
    socket.on('disconnect', function() {
      socket.disconnect();
      connected = false;
      // Try to reconnect.
      setTimeout(function() {
        if (socket.io.uri === urls[urlIndex]) {
          connect((urlIndex + 1) % urls.length);
        }
      }, 1000);
    });
  }

  connect(0);

  // Assign the disconnect method to the variable.
  disconnectFn = function() {
    socket.disconnect();
  }
};



disconnectSocket = function() {
  disconnectFn();
}

let disconnectFnAnon;

txMonitorAnon = function() {
    eventToListenTo = 'anon'
    room = {"username": Math.floor(Math.random() * 100000000).toString(), "room": "tx"}

    var socket = io("http://127.0.0.1:5000/");
    //var socket = io("https://api.tuxprint.com:52556/");
    socket.on('connect', function() {
      // Join the room.
      socket.emit('join', room);
    })
    socket.on(eventToListenTo, function(data) {
      console.log(data);
      //pything = pyscript.runtime.globals.get('newTx');
      //pything(data);
    })

    socket.on("room_message", function(data) {
      console.log(data);
      //pything = pyscript.runtime.globals.get('newTx');
      //pything(data);
    })

    // Assign the disconnect method to the variable.
    disconnectFnAnon = function() {
      socket.disconnect();
    }
};

disconnectSocketAnon = function() {
  disconnectFnAnon();
}

browserType = function() {
    let userAgent = navigator.userAgent;
         let browserName;
         
         if(userAgent.match(/chrome|chromium|crios/i)){
             if(navigator.brave && navigator.brave.isBrave()) {
              browserName = "brave";
             } else if(userAgent.match(/edg/i)){
                browserName = "edge";
              }else{
                browserName = "chrome";
              }
           }else if(userAgent.match(/firefox|fxios/i)){
             browserName = "firefox";
           }  else if(userAgent.match(/safari/i)){
             browserName = "safari";
           }else if(userAgent.match(/opr\//i)){
             browserName = "opera";
           } else{
             browserName="No browser detection";
           };

        return browserName;
};

getOS = function() {
  var userAgent = navigator.userAgent;
  var os = null;

  if(userAgent.match(/Macintosh|MacIntel|MacPPC|Mac68K/i)){
    os = "MacOs";
  }else if(userAgent.match(/Win32|Win64|Windows|WinCE/i)){
    os = "Windows";
  }  else if(userAgent.match(/Android/i)){
    os = "Android";
  }else if(userAgent.match(/Linux/i)){
    os = "Linux";
  } else if(userAgent.match(/iPhone|iPad|iPod/i)){
    os = "iOS";
  }else{
    os="No os detected";
  };

  return os;
};

validateAddress = function(addr) {

    return bitcore.Address.isValid(addr)

};

isValidAddr256 = function(addr) {

    if (bitcore.Address.isValid(addr)) {
        return bitcore.Address(addr).isPayToPublicKeyHash256()
    } else {
      return false
    };
};

isValidURI = function(uri) {
    return bitcore.URI.isValid(uri);
}


decodeURI = function(uriString) {
    var uri = new bitcore.URI(uriString);

    return {"address": uri.address.toString(), "amount": uri.amount}
}

getCsAddrInfo = function(coldStakingAddress) {
  try {
  var addr = bech32.decode(coldStakingAddress);
    csa = {
      hashBuffer: Buffer.from(addr.data)
    };
    if (addr.prefix == "gcs"){
      return {
       "isValid": true,
       "type": "bech32" 
      }
    } else {
      return {"isValid": false}
    }
    } catch {
        try {
          bitcore.HDPublicKey(coldStakingAddress)
          return {
            "isValid": true,
            "type": "xpub" 
           }
        } catch {
          return {"isValid": false}
        }
    }
};



clickTXIDjs = function (txid) {
  pything = pyscript.runtime.globals.get('clickTXID');
      pything(txid);
};

copyUsedAddrjs = function (addr) {
  pything = pyscript.runtime.globals.get('copyUsedAddr');
      pything(addr);
};

var xDown = null;
var yDown = null;
var xDiff = null;
var yDiff = null;
var MIN_SWIPE_DISTANCE = 10; // minimum swipe distance in pixels

function getTouches(evt) {
  return evt.touches || evt.originalEvent.touches;
}

handleTouchStart = function (evt) {
  const firstTouch = getTouches(evt)[0];
  xDown = firstTouch.clientX;
  yDown = firstTouch.clientY;
};

handleTouchMove = function (evt) {
  if (!xDown || !yDown) {
    return;
  }

  var xUp = evt.touches[0].clientX;
  var yUp = evt.touches[0].clientY;

  xDiff = xDown - xUp;
  yDiff = yDown - yUp;

  if (Math.abs(xDiff) > MIN_SWIPE_DISTANCE || Math.abs(yDiff) > MIN_SWIPE_DISTANCE) {
    if (Math.abs(xDiff) > Math.abs(yDiff)) {
      if (xDiff > 0) {
        //console.log("Left swipe detected");
        pything = pyscript.runtime.globals.get('swipeLeft');
                          pything();
      } else {
        //console.log("Right swipe detected");
        pything = pyscript.runtime.globals.get('swipeRight');
                          pything();
      }
    } else {
      if (yDiff > 0) {
        //console.log("Up swipe detected");
      } else {
        //console.log("Down swipe detected");
      }
    }
  }

  xDown = null;
  yDown = null;
};


poolRadio = function(thing) {
  pything = pyscript.runtime.globals.get('setPoolOption');
                          pything(thing.value);
}


doZapjs = function () {
  pything = pyscript.runtime.globals.get('doZap');
                          pything();
}

txInfojs = function (txid) {
  pything = pyscript.runtime.globals.get('txInfo');
                          pything(txid);
}


fiatRadio = function(thing) {
  pything = pyscript.runtime.globals.get('setFiatOption');
                          pything(thing.value);
}

csAddrRadio = function(thing) {
  pything = pyscript.runtime.globals.get('setSpendAddr');
                          pything(thing.value);
}

explorerRadio = function(thing) {
  pything = pyscript.runtime.globals.get('setExplorerOption');
                          pything(thing.value);
}

langRadio = function(thing) {
  pything = pyscript.runtime.globals.get('setLangOption');
                          pything(thing.value);
}

closeMessageBox = function(isTxSuccess=false) {
    pything = pyscript.runtime.globals.get('closeMessageBox');
    
    if (!isTxSuccess) {
      pything();
    } else {
      pything(true)
    }

}

finalizeSendTx = function() {
    pything = pyscript.runtime.globals.get('finalizeSendTx');
    pything();

}

getNextTxPagejs = function() {
  pything = pyscript.runtime.globals.get('getNextTxPage');
    pything();
}

var screenHideTime = 0;
var idleTime = 0;
var hiddenStartTime = 0;

window.onbeforeunload = function() {
  console.log(isDupe);

  if (idleTime >= 10 || screenHideTime >= 5){
    return
  };

  if (!isDupe) {
    return "Dude, are you sure you want to leave? Think of the kittens!";
  };
}


idleTimer = function() {
  $(document).ready(function () {
      // Increment the idle time counter every minute.
      var idleInterval = setInterval(timerIncrement, 60000); // 1 minute

      // Zero the idle timer on mouse movement and touch events.
      $(this).on("mousemove touchstart", function (e) {
          idleTime = 0;
          //console.log("mouse move/touchstart");
      });
      $(this).keypress(function (e) {
          idleTime = 0;
          //console.log("key press");
      });
  });
}

function timerIncrement() {
    idleTime = idleTime + 1;
    //console.log("plus one min");
    if (idleTime >= 10) { // 10 minutes
        window.location.reload();
    }
}


screenHideEvent = function() {
  $(document).ready(function () {
    // Increment the idle time counter every minute.
    var idleInterval = setInterval(screenHideTimerIncrement, 60000); // 60 seconds
  
    // Zero the idle timer on mouse movement and touch events.
    $(document).on("visibilitychange", function (e) {
      screenHideTime = 0;
      //console.log("visibility has changed")
      if (document.hidden) {
        hiddenStartTime = Date.now();
          } else {
            //console.log("Page is now visible");
            if (Date.now() - hiddenStartTime >= 300000) {
              //console.log("Page has been hidden for 5 minutes");
              screenHideTime = 5;
              window.location.reload();
            } else {
              hiddenStartTime = 0;
              screenHideTime = 0;
            }
          }
      
    });
  });
}


function screenHideTimerIncrement() {
  if (document.hidden) {
    //console.log("screen been hidden for a minute.")
    screenHideTime = screenHideTime + 1;
    if (screenHideTime >= 5) { // 5 minutes
      // Perform the action
      console.log("The screen has been hidden for 4.5 minutes");
      window.location.reload();
    }
  } else {
    screenHideTime = 0;
  }
}

let html5QrcodeScanner;

// Start the scanner.
scanQRCode = function () {
  html5QrcodeScanner = new Html5QrcodeScanner(
    "camera-stream",
    { fps: 10, qrbox: { width: 250, height: 250 }, aspectRatio: 0.75, direction: "environment" },
    false
  );

  html5QrcodeScanner.render(
    (qrCodeMessage) => {
      console.log(`QR code detected: ${qrCodeMessage}`);
      pything = pyscript.runtime.globals.get('parseScanner');
          pything(qrCodeMessage);
      //stopScanner();
    },
    (errorMessage) => {
      console.error(errorMessage);
    }
  );
};

// Stop the scanner.
stopScanner = function () {
  if (html5QrcodeScanner) {
    html5QrcodeScanner.clear();
    html5QrcodeScanner = null;
  }
};
