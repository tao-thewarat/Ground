/** @type {import('prettier').Config} */

const config = {
  // https://github.com/prettier/prettier/issues/15388#issuecomment-1717746872
  plugins: [require.resolve("@prettier/plugin-xml")],
  tabWidth: 4,
  useTabs: false,
  printWidth: 88,
  semi: true,
  trailingComma: "es5",
  bracketSpacing: false,
  xmlWhitespaceSensitivity: "preserve",
}

module.exports = config
