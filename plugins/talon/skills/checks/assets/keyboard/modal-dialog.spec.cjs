const { expect, test } = require('@playwright/test');

const settingsPath = '/settings';
const tabPressesToOpener = 1;
const dialogTestId = 'profile-dialog';

async function openProfileDialog(page) {
  await page.goto(settingsPath);

  const opener = page.getByRole('button', { name: 'Изменить профиль', exact: true });
  const dialogContainer = page.getByTestId(dialogTestId);
  const dialog = dialogContainer.and(page.getByRole('dialog', {
    name: 'Изменение профиля',
    exact: true,
  }));
  const name = dialog.getByRole('textbox', { name: 'Имя', exact: true });
  const cancel = dialog.getByRole('button', { name: 'Отмена', exact: true });
  const save = dialog.getByRole('button', { name: 'Сохранить', exact: true });

  for (let step = 0; step < tabPressesToOpener; step++) {
    await page.keyboard.press('Tab');
  }
  await expect(opener, 'Кнопка открытия достижима через Tab').toBeFocused();
  await page.keyboard.press('Enter');
  await expect(dialog, 'Enter открывает диалог с доступным названием').toBeVisible();

  return { opener, dialogContainer, name, cancel, save };
}

test('при открытии фокус переходит в поле «Имя»', async ({ page }) => {
  const { name } = await openProfileDialog(page);

  await expect(name, 'Фокус при открытии диалога').toBeFocused();
});

test('Tab проходит диалог и возвращает фокус с конца в начало', async ({ page }) => {
  const { name, cancel, save } = await openProfileDialog(page);

  await page.keyboard.press('Tab');
  await expect(cancel, 'Tab переводит фокус с поля на «Отмена»').toBeFocused();
  await page.keyboard.press('Tab');
  await expect(save, 'Tab переводит фокус с «Отмена» на «Сохранить»').toBeFocused();
  await page.keyboard.press('Tab');
  await expect(name, 'Tab на последнем элементе возвращает фокус на первый').toBeFocused();
});

test('Shift+Tab проходит диалог и переносит фокус с начала в конец', async ({ page }) => {
  const { name, cancel, save } = await openProfileDialog(page);

  await page.keyboard.press('Shift+Tab');
  await expect(save, 'Shift+Tab на первом элементе переносит фокус на последний').toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(cancel, 'Shift+Tab переводит фокус с «Сохранить» на «Отмена»').toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(name, 'Shift+Tab переводит фокус с «Отмена» на поле').toBeFocused();
});

test('Escape закрывает диалог', async ({ page }) => {
  const { dialogContainer } = await openProfileDialog(page);

  await page.keyboard.press('Escape');
  await expect(dialogContainer, 'После Escape диалог скрыт или удалён').toBeHidden();
});

test('Escape возвращает фокус на кнопку открытия', async ({ page }) => {
  const { opener, name } = await openProfileDialog(page);
  await expect(name, 'Перед Escape фокус находится в диалоге').toBeFocused();

  await page.keyboard.press('Escape');
  await expect(opener, 'Фокус после выхода из диалога').toBeFocused();
});
