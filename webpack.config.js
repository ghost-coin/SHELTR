var path = require('path');

module.exports = {
  entry: './SHELTRjs/app.js',
  output: {
    path: path.resolve(__dirname),
    filename: 'SHELTRjs/_bundle.js'
  }
};
